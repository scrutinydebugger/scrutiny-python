import uuid
import logging
import json
import threading
import socket
from dataclasses import dataclass
import time
import traceback
import queue

from scrutiny.server.api.abstract_client_handler import AbstractClientHandler, ClientHandlerConfig, ClientHandlerMessage
from scrutiny.tools.stream_datagrams import StreamMaker, StreamParser

from typing import Dict, Any, Optional, TypedDict, cast


class TCPClientHandlerConfig(TypedDict):
    host:str
    port:int

@dataclass
class ThreadBasics:
    thread:threading.Thread
    started_event:threading.Event
    stop_event:threading.Event

@dataclass
class ClientInfo:
    sock:socket.socket
    conn_id:str
    thread_info:ThreadBasics

class TCPClientHandler(AbstractClientHandler):
    STREAM_MTU = 1024*1024
    STREAM_INTERCHUNK_TIMEOUT = 1.0
    STREEAM_USE_HASH = True


    config: TCPClientHandlerConfig
    logger: logging.Logger
    rx_event:Optional[threading.Event]
    server_thread:Optional[ThreadBasics]
    server_sock:Optional[socket.socket]

    id2client_map:Dict[str, ClientInfo]
    rx_queue:queue.Queue[ClientHandlerMessage]
    stream_maker:StreamMaker

    def __init__(self, config: ClientHandlerConfig, rx_event:Optional[threading.Event]=None):
        if 'host' not in config:
            raise ValueError('Missing host in config')
        if 'port' not in config:
            raise ValueError('Missing port in config')
        
        self.config = {
            'host' : str(config['host']),
            'port' : int(config['port']),
        }
        self.logger = logging.getLogger(self.__class__.__name__)
        self.rx_event=rx_event
        self.server_thread = None
        self.id2client_map = {}
        self.server_sock = None
        self.stream_maker = StreamMaker(
            mtu=self.STREAM_MTU,
            use_hash=self.STREEAM_USE_HASH
            )
        
    def send(self, msg: ClientHandlerMessage) -> None:
        try:
            # Using try/except to avoid race condition if the server thread deletes the client while sending
            client = self.id2client_map[msg.conn_id]    
        except KeyError:
            self.logger.error(f"Trying to send to inexistent client with ID {msg.conn_id}")
        
        try:
            payload = self.stream_maker.encode(json.dumps(msg.obj))
            client.sock.send(payload)
        except Exception as e:
            self.logger.error(f"Failed to send message to client {msg.conn_id}. {e}")
            self.logger.debug(traceback.format_exc())
        

    def start(self) -> None:
        self.logger.info('Starting websocket listener on %s:%s' % (self.config['host'], self.config['port']))
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.bind((self.config['host'], self.config['port']))
        self.server_sock.listen()

        self.server_thread = ThreadBasics(
            thread=threading.Thread(target=self.st_server_thread_fn),
            started_event=threading.Event(),
            stop_event=threading.Event()
        )
        self.server_thread.thread.start()
        self.server_thread.started_event.wait()

    def stop(self) -> None:
        self._stop_internal(join=True)

    def _stop_internal(self, join:bool=True) -> None:
        for conn_id in list(self.id2client_map.keys()):
            self.unregister_client(conn_id)

        if self.server_thread is not None:
            self.server_thread.stop_event.set()
            if self.server_sock is not None:
                self.server_sock.close()
            if join:
                self.server_thread.thread.join(2)
                if self.server_thread.thread.is_alive():
                    self.logger.error("Failed to stop the server. Join timed out")

        self.server_thread = None
        self.server_sock = None
        while not self.rx_queue.empty():
            self.rx_queue.get()


    def process(self) -> None:
        # cleanup dead clients in the main thread
        for conn_id in list(self.id2client_map.keys()):
            if not self.is_connection_active(conn_id):
                self.unregister_client(conn_id)


    def available(self) -> bool:
        return not self.rx_queue.empty()

    def recv(self) -> Optional[ClientHandlerMessage]:
        try:
            return self.rx_queue.get_nowait()
        except queue.Empty:
            return None

    def is_connection_active(self, conn_id: str) -> bool:
        """Tells if a client connection is presently functional and alive"""
        try:
            client = self.id2client_map[conn_id]
        except KeyError:
            return False
        
        # If the socket dies, the client thread will exit
        if not client.thread_info.thread.is_alive():
            return False
        
        return True


    def st_server_thread_fn(self) -> None:
        """The server thread accepting connections and spawning client threads"""
        if self.server_thread is None:
            return
        self.server_thread.started_event.set()
        while not self.server_thread.stop_event.is_set():
            try:
                sock, addr = self.server_sock.accept()
                conn_id = uuid.uuid4().hex
                self.logger.debug(f"Accepted incoming connection from {addr}. Assigned ID {conn_id}")
                self.st_register_client(conn_id, sock)
            except Exception as e:
                self.logger.error(str(e))
                self.logger.debug(traceback.format_exc())
                self._stop_internal(join=False)
    
    def ct_client_thread_fn(self, conn_id:str, sock:socket.socket, started_event:threading.Event, stop_event:threading.Event) -> None:
        """The thread dedicated to reading the client socket.
            Exit if the socket becomes invalid
        """
        started_event.set()
        parser = StreamParser(mtu=self.STREAM_MTU, interchunk_timeout=self.STREAM_INTERCHUNK_TIMEOUT, use_hash=self.STREEAM_USE_HASH)
        q = parser.queue()
        while not stop_event.is_set():
            try:
                data = sock.recv(4096)
            except socket.error:
                break   # Exit the thread. The main thread will cleanup by checking is_alive()
                
            parser.parse(data)
            has_received_data=False
            while not q.empty():
                msg = q.get()
                try:
                    obj = json.loads(msg.decode('utf8'))
                except json.JSONDecodeError as e:
                    self.logger.error('Received malformed JSON. %s' % str(e))
                    if msg:
                        self.logger.debug(msg)
                    continue
                has_received_data = True
                self.rx_queue.put((conn_id, obj))
            
            if self.rx_event is not None and has_received_data:
                self.rx_event.set() # The main thread release the CPU by waiting for that event.

            
    def st_register_client(self, conn_id:str, sock:socket.socket) -> None:
        """Register a client. Called by the server thread (st)."""
        stop_event = threading.Event()
        started_event = threading.Event()
        client_thread = ThreadBasics(
            threading.Thread(target=self.ct_client_thread_fn, args=[conn_id, sock, started_event, stop_event]),
            started_event=started_event,
            stop_event=stop_event
        )

        client = ClientInfo(
            sock = sock,
            conn_id=conn_id,
            thread_info=client_thread
        )
        self.id2client_map[conn_id] = client

        client_thread.thread.start()
        client_thread.started_event.wait()

    
    def unregister_client(self, conn_id:str) -> None:
        """Close the communication with a client and clear internal entry"""
        try:
            client = self.id2client_map[conn_id]
        except KeyError:
            return
        
        self.logger.debug(f"Unregistering client with id {conn_id}")
        client.thread_info.stop_event.set()
        client.sock.close()
        client.thread_info.thread.join(timeout=2)
        if client.thread_info.thread.is_alive():
            self.logger.error("Failed to join the client thread while unregistering client {client_id}")

        try:
            del self.id2client_map[conn_id]
        except KeyError:
            pass
