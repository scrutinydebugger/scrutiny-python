#    tcp_client_handler.py
#        The connection manager used by the aPI that manages multi-clients. Listen on TCP
#        sockets
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = [
    'ClientInfo',
    'TCPClientHandler'
]

import uuid
import logging
import json
import threading
import socket
from dataclasses import dataclass
import queue
import selectors
import time

from scrutiny.server.api.abstract_client_handler import AbstractClientHandler, ClientHandlerConfig, ClientHandlerMessage
from scrutiny.tools.stream_datagrams import StreamMaker, StreamParser
from scrutiny.core.logging import DUMPDATA_LOGLEVEL
from scrutiny.tools.profiling import VariableRateExponentialAverager
from scrutiny import tools

from scrutiny.tools.typing import *


class TCPClientHandlerConfig(TypedDict):
    host: str
    port: int


@dataclass
class _ThreadBasics:
    thread: threading.Thread
    started_event: threading.Event
    stop_event: threading.Event


@dataclass
class ClientInfo:
    sock: socket.socket
    conn_id: str


class TCPClientHandler(AbstractClientHandler):
    STREAM_MTU = 1024 * 1024
    STREAM_INTERCHUNK_TIMEOUT = 1.0
    STREAM_USE_HASH = True
    STREAM_USE_COMPRESSION = True
    READ_SIZE = 4096

    config: TCPClientHandlerConfig
    logger: logging.Logger
    rx_event: Optional[threading.Event]
    server_thread_info: Optional[_ThreadBasics]
    server_sock: Optional[socket.socket]
    selector: Optional[selectors.DefaultSelector]

    id2sock_map: Dict[str, socket.socket]
    sock2id_map: Dict[socket.socket, str]
    rx_queue: "queue.Queue[ClientHandlerMessage]"
    stream_maker: StreamMaker

    index_lock: threading.Lock
    force_silent: bool  # For unit testing of timeouts
    rx_datarate_measurement: VariableRateExponentialAverager
    tx_datarate_measurement: VariableRateExponentialAverager

    rx_msg_count: int
    tx_msg_count: int

    def __init__(self, config: ClientHandlerConfig, rx_event: Optional[threading.Event] = None):
        super().__init__(config, rx_event)
        if 'host' not in config:
            raise ValueError('Missing host in config')
        if 'port' not in config:
            raise ValueError('Missing port in config')

        self.config = {
            'host': str(config['host']),
            'port': int(config['port'])
        }
        self.logger = logging.getLogger(self.__class__.__name__)
        self.rx_event = rx_event
        self.server_thread_info = None
        self.id2sock_map = {}
        self.sock2id_map = {}
        self.server_sock = None
        self.selector = None
        self.stream_maker = StreamMaker(
            mtu=self.STREAM_MTU,
            use_hash=self.STREAM_USE_HASH
        )
        self.rx_queue = queue.Queue()
        self.index_lock = threading.Lock()
        self.force_silent = False
        self.rx_datarate_measurement = VariableRateExponentialAverager(time_estimation_window=0.1, tau=0.5, near_zero=1)
        self.tx_datarate_measurement = VariableRateExponentialAverager(time_estimation_window=0.1, tau=0.5, near_zero=1)
        self.rx_msg_count = 0
        self.tx_msg_count = 0

    def send(self, msg: ClientHandlerMessage) -> None:
        assert isinstance(msg, ClientHandlerMessage)
        try:
            # Using try/except to avoid race condition if the server thread deletes the client while sending
            sock = self.id2sock_map[msg.conn_id]
        except KeyError:
            self.logger.error(f"Trying to send to inexistent client with ID {msg.conn_id}")
            return

        data = json.dumps(msg.obj, indent=None, separators=(',', ':')).encode('utf8')
        payload = self.stream_maker.encode(data)
        self.logger.log(DUMPDATA_LOGLEVEL, f"Sending {len(payload)} bytes to client ID: {msg.conn_id}")

        try:
            if not self.force_silent:
                self.tx_datarate_measurement.add_data(len(payload))
                sock.send(payload)
                self.tx_msg_count += 1
        except OSError:
            # Client is gone. Did not get cleaned by the server thread. Should not happen.
            self.unregister_client(msg.conn_id)

    def get_port(self) -> Optional[int]:
        if self.server_sock is None:
            return None

        _, port = self.server_sock.getsockname()
        return cast(int, port)

    def start(self) -> None:
        self.last_process = time.perf_counter()
        self.logger.info('Starting TCP socket listener on %s:%s' % (self.config['host'], self.config['port']))
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.config['host'], self.config['port']))
        self.server_sock.listen()
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.server_sock, selectors.EVENT_READ)

        self.server_thread_info = _ThreadBasics(
            thread=threading.Thread(target=self.st_server_thread_fn),
            started_event=threading.Event(),
            stop_event=threading.Event()
        )
        self.server_thread_info.thread.start()
        self.server_thread_info.started_event.wait()
        self.rx_datarate_measurement.enable()
        self.tx_datarate_measurement.enable()

    def stop(self) -> None:
        self.rx_datarate_measurement.disable()
        self.tx_datarate_measurement.disable()
        if self.server_thread_info is not None:
            self.server_thread_info.stop_event.set()
            if self.server_sock is not None:
                self.server_sock.close()    # Will wake up the server thread
            server_thread_obj = self.server_thread_info.thread
            server_thread_obj.join(2)
            if server_thread_obj.is_alive():
                self.logger.error("Failed to stop the server. Join timed out")

        while not self.rx_queue.empty():
            self.rx_queue.get()

        for client_id in self.get_client_list():
            self.unregister_client(client_id)

        if self.selector is not None:
            self.selector.close()

        self.server_thread_info = None
        self.server_sock = None
        self.selector = None

    def process(self) -> None:
        self.rx_datarate_measurement.update()
        self.tx_datarate_measurement.update()

    def available(self) -> bool:
        return not self.rx_queue.empty()

    def recv(self) -> Optional[ClientHandlerMessage]:
        try:
            return self.rx_queue.get_nowait()
        except queue.Empty:
            return None

    def is_connection_active(self, conn_id: str) -> bool:
        """Tells if a client connection is presently functional and alive"""
        with self.index_lock:
            try:
                sock = self.id2sock_map[conn_id]
            except KeyError:
                return False

        if sock.fileno() == -1:
            return False

        return True

    def get_number_client(self) -> int:
        with self.index_lock:
            return len(self.id2sock_map)

    @classmethod
    def get_compatible_stream_parser(cls) -> StreamParser:
        return StreamParser(
            mtu=cls.STREAM_MTU,
            interchunk_timeout=cls.STREAM_INTERCHUNK_TIMEOUT
        )

    @classmethod
    def get_compatible_stream_maker(cls) -> StreamMaker:
        return StreamMaker(
            mtu=cls.STREAM_MTU,
            use_hash=cls.STREAM_USE_HASH,
            compress=cls.STREAM_USE_COMPRESSION
        )

    def st_server_thread_fn(self) -> None:
        """The server thread accepting connections and spawning client threads"""
        if self.server_thread_info is None:
            return
        assert self.server_sock is not None
        assert self.selector is not None
        stream_parser = StreamParser(
            mtu=self.STREAM_MTU,
            interchunk_timeout=self.STREAM_INTERCHUNK_TIMEOUT,
        )

        try:
            self.server_thread_info.started_event.set()
            while not self.server_thread_info.stop_event.is_set():
                events = self.selector.select(timeout=0.2)
                new_data = False
                for key, _ in events:
                    if key.fileobj is self.server_sock:
                        try:
                            sock, addr = self.server_sock.accept()
                        except OSError as e:
                            # Server socket was closed. Someone must have called stop()
                            self.logger.debug("Server socket is closed. Exiting server thread")
                            self.server_thread_info.stop_event.set()
                            break

                        self.st_register_client(sock, addr)
                        self.selector.register(sock, selectors.EVENT_READ)
                    else:
                        client_socket = cast(socket.socket, key.fileobj)
                        try:
                            client_id = self.sock2id_map[client_socket]
                        except KeyError:
                            self.logger.critical("Received message from unregistered socket")
                            # Race condition possible here
                            with tools.SuppressException():
                                self.selector.unregister(client_socket)
                            continue

                        try:
                            data = client_socket.recv(self.READ_SIZE)
                        except OSError:
                            # Socket got closed
                            self.unregister_client(client_id)
                            continue

                        if not data:
                            # Client is gone
                            self.unregister_client(client_id)
                        else:
                            self.rx_datarate_measurement.add_data(len(data))
                            self.logger.log(DUMPDATA_LOGLEVEL, f"Received {len(data)} bytes from client ID: {client_id}")
                            stream_parser.parse(data)
                            while not stream_parser.queue().empty():
                                datagram = stream_parser.queue().get()
                                try:
                                    obj = json.loads(datagram.decode('utf8'))
                                except json.JSONDecodeError as e:
                                    tools.log_exception(self.logger, e, f"Received malformed JSON from client {client_id}.")
                                    continue

                                self.rx_queue.put(ClientHandlerMessage(conn_id=client_id, obj=obj))
                                self.rx_msg_count += 1
                                new_data = True
                if new_data and self.rx_event is not None:
                    self.rx_event.set()

        except Exception as e:
            tools.log_exception(self.logger, e, "Unexpected error in server thread")
        finally:
            for conn_id in list(self.id2sock_map.keys()):
                self.unregister_client(conn_id)

    def get_client_list(self) -> List[str]:
        with self.index_lock:
            return list(self.id2sock_map.keys())

    def st_register_client(self, sock: socket.socket, sockaddr: str) -> str:
        """Register a client. Called by the server thread (st)."""
        conn_id = uuid.uuid4().hex
        with self.index_lock:
            self.id2sock_map[conn_id] = sock
            self.sock2id_map[sock] = conn_id

        self.logger.info(f"New client connected {sockaddr} (ID={conn_id}). {len(self.id2sock_map)} clients total")

        try:
            self.new_conn_queue.put(conn_id)
        except queue.Full:
            self.logger.error(f"Failed to inform the API of the new connection {conn_id}. Queue full")

        return conn_id

    def unregister_client(self, conn_id: str) -> None:
        """Close the communication with a client and clear internal entry"""
        with self.index_lock:
            try:
                sock = self.id2sock_map[conn_id]
            except KeyError:
                return

            sockaddr: Optional[Tuple[str, int]] = None
            with tools.SuppressException(OSError):
                sockaddr = sock.getsockname()
                sock.close()

            with tools.SuppressException(KeyError):
                if self.selector is not None:
                    self.selector.unregister(sock)

            with tools.SuppressException(KeyError):
                del self.id2sock_map[conn_id]

            with tools.SuppressException(KeyError):
                del self.sock2id_map[sock]

            nb_client = len(self.id2sock_map)

        sockaddr_str = str(sockaddr) if sockaddr is not None else ""
        self.logger.info(f"Client disconnected {sockaddr_str} (ID={conn_id}). {nb_client} clients total")

    def get_stats(self) -> AbstractClientHandler.Statistics:
        return AbstractClientHandler.Statistics(
            client_count=self.get_number_client(),
            input_datarate_byte_per_sec=self.rx_datarate_measurement.get_value(),
            output_datarate_byte_per_sec=self.tx_datarate_measurement.get_value(),
            msg_received=self.rx_msg_count,
            msg_sent=self.tx_msg_count,
        )
