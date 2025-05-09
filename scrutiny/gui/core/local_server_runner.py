from PySide6.QtCore import Signal, QObject, SignalInstance

import subprocess
import threading
import sys
import scrutiny
import os
import logging
import enum
import signal

from scrutiny.tools.typing import *
from scrutiny.tools.thread_enforcer import enforce_thread
from scrutiny import tools

from scrutiny.gui.core.threads import QT_THREAD_NAME

class LocalServerRunner:
    """A class that can run a instance of the server in a subprocess"""
    
    class State(enum.Enum):
        """The state of the subprocess"""
        STOPPED = enum.auto()
        STARTING = enum.auto()
        STARTED = enum.auto()
        STOPPING = enum.auto()
    
    class _Signals(QObject):
        stdout = Signal(str)
        stderr = Signal(str)
        state_changed = Signal(object)
        abnormal_termination = Signal()
    
    class _InternalSignals(QObject):
        spawned = Signal()
        exit = Signal()

    _logger:logging.Logger
    """The logger"""
    _owner_thread:Optional[threading.Thread]
    """The thread that will run and monitor the state of the subprocess"""
    _signals:_Signals
    """The QT signals"""
    _internal_signals:_InternalSignals
    """Internal QT signals for synchronization"""
    _state: State
    """The actual state of the local server"""
    _stop_event:threading.Event
    """A threading event to trigger the termination of the internal thread and exit the local server """
    _active_process:Optional[subprocess.Popen[bytes]]
    """The process of the local server"""

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._owner_thread = None
        self._signals = self._Signals()
        self._internal_signals = self._InternalSignals()
        self._state = self.State.STOPPED
        self._stop_event = threading.Event()
        self._active_process = None
        
        self._internal_signals.exit.connect(self._exit_slot)
        self._internal_signals.spawned.connect(self._spawed_slot)

    @property
    def signals(self) -> _Signals:
        return self._signals
    
    def _exit_slot(self) -> None:
        self._set_state(self.State.STOPPED)
    
    def _spawed_slot(self) -> None:
        self._set_state(self.State.STARTED)
    
    def _set_state(self, new_state:State) -> None:
        changed = new_state != self._state
        self._state = new_state
        if changed:
            self._signals.state_changed.emit(new_state)

    @enforce_thread(QT_THREAD_NAME)
    def start(self, port:int) -> None:
        """Start the local server. Does nothing if not fully stopped.
        Moves the state from STOPPED to STARTING
        """
        assert isinstance(port, int)
        self._logger.debug("Requesting to start")
        if self._state != self.State.STOPPED:
            self._logger.debug("Already started")
            return
        
        self._set_state(self.State.STARTING)
        self._owner_thread = threading.Thread(target=self._thread_func, daemon=True, args=[port])
        
        self._stop_event.clear()
        self._owner_thread.start()
    
    @enforce_thread(QT_THREAD_NAME)
    def stop(self) -> None:
        """Request the server to stop.
        Moves the state from STARTING/STARTED to STOPPING
        """
        self._logger.debug("Requesting to stop")
        self._stop_event.set()
        if self._state in (self.State.STOPPING, self.State.STOPPED):
            self._logger.debug("Already stopped")
            return 
        
        self._set_state(self.State.STOPPING)
        
    def _thread_func(self, port:int) -> None:
        """The thread function that monitor the subprocess"""
        # Copy the environment for the subprocess
        env = os.environ.copy()
        if 'PYTHONPATH' not in env:
            env['PYTHONPATH'] = ''
        # Make sure we run exactly the same installation of scrutiny
        env['PYTHONPATH'] = os.path.dirname(scrutiny.__file__) + ':' +  env['PYTHONPATH']

        try:
            options = [f'api.client_interface_config.port={port}']
            process = subprocess.Popen(
                [sys.executable, '-m', 'scrutiny', 'server', '--options'] + options, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                shell=False,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,  # Important for windows. Ctrl+Break will hit the parent process otherwise
                env=env)
            
            def read_stream(stream:IO[bytes], signal:SignalInstance) -> None:
                while True:
                    line = stream.readline().decode('utf8')
                    line = line.strip()
                    if len(line) > 0:
                        signal.emit(line)
                    elif process.poll() is not None:
                        break
                
            def read_stdout() -> None:
                assert process.stdout is not None
                read_stream(process.stdout, self._signals.stdout)
                self._logger.debug(f"stdout reader exit")

            def read_stderr() -> None:
                assert process.stderr is not None
                read_stream(process.stderr, self._signals.stderr)
                self._logger.debug(f"stderr reader exit")

            stdout_reader_thread = threading.Thread(target=read_stdout, daemon=True)
            stderr_reader_thread = threading.Thread(target=read_stderr, daemon=True)
            stdout_reader_thread.start()
            stderr_reader_thread.start()

            self._active_process = process
            self._internal_signals.spawned.emit()   # Will change the state to STARTED in the QT thread.

            # Process is started and running
            while True:
                self._stop_event.wait(0.5)
                if self._stop_event.is_set():
                    break
                if process.poll() is not None:
                    # The process died by itself.
                    self.signals.abnormal_termination.emit()
                    break
                
            if process.poll() is None:   # Still running
                self._logger.debug("Terminating process")
                if sys.platform == 'win32':
                    # Ctrl+Break is the only signal that seems to be catchable on windows.
                    # I don't understand Windows.
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    process.send_signal(signal.SIGTERM)
                process.wait(5)
            else:
                # Already dead. Do nothing
                pass

        except Exception as e:
            # Something unusual happened
            tools.log_exception(self._logger, e, "Exception in local server thread")
            if self._active_process is not None:
                self._active_process.terminate()    # SIGTERM or Win32 Hard kill

        self._active_process = None
        self._internal_signals.exit.emit()  # Will set the state to STOPPED in the QT thread
    
    def __del__(self) -> None:
        # Safety
        if  self._active_process is not None:
            self._active_process.terminate()    # SIGTERM or Win32 Hard kill
            self._active_process = None
        
