#    tcp_client_handler.py
#        The connection manager used by the aPI that manages multi-clients. Listen on TCP
#        sockets
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import uuid
import logging
import json
import threading
import socket
from dataclasses import dataclass
import traceback
import queue

from scrutiny.server.api.abstract_client_handler import AbstractClientHandler, ClientHandlerConfig, ClientHandlerMessage
from scrutiny.tools.stream_datagrams import StreamMaker, StreamParser
import selectors

from typing import Dict, Any, Optional, TypedDict, cast, List


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

class TCPClientHandler(AbstractClientHandler):
    STREAM_MTU = 1024*1024
    STREAM_INTERCHUNK_TIMEOUT = 1.0
    STREAM_USE_HASH = True
    READ_SIZE = 4096

    config: TCPClientHandlerConfig
    logger: logging.Logger
    rx_event:Optional[threading.Event]
    server_thread_info:Optional[ThreadBasics]
    server_sock:Optional[socket.socket]

    id2sock_map:Dict[str, socket.socket]
    sock2id_map:Dict[socket.socket, str]
    rx_queue:queue.Queue[ClientHandlerMessage]
    stream_maker:StreamMaker

    registry_lock:threading.Lock
    force_silent: bool  # For unit testing of timeouts

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
        self.server_thread_info = None
        self.id2sock_map = {}
        self.sock2id_map = {}
        self.server_sock = None
        self.stream_maker = StreamMaker(
            mtu=self.STREAM_MTU,
            use_hash=self.STREAM_USE_HASH
            )
        self.rx_queue = queue.Queue()
        self.registry_lock = threading.Lock()
        self.force_silent = False
        
    def send(self, msg: ClientHandlerMessage) -> None:
        assert isinstance(msg, ClientHandlerMessage)
        try:
            # Using try/except to avoid race condition if the server thread deletes the client while sending
            sock = self.id2sock_map[msg.conn_id]    
        except KeyError:
            self.logger.error(f"Trying to send to inexistent client with ID {msg.conn_id}")
            return
        

        payload = self.stream_maker.encode(json.dumps(msg.obj).encode('utf8'))
        self.logger.debug(f"Sending {len(payload)} bytes to client ID: {msg.conn_id}")

        try:
            if not self.force_silent:
                sock.send(payload)
        except OSError:
            # Client is gone. Did not get cleaned by the server thread. Should ot happen.
            self.unregister_client(msg.conn_id)
            
    
    def get_port(self) -> Optional[int]:
        if self.server_sock is None:
            return None
        
        _, port = self.server_sock.getsockname()
        return cast(int, port)

    def start(self) -> None:
        self.logger.info('Starting TCP socket listener on %s:%s' % (self.config['host'], self.config['port']))
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.bind((self.config['host'], self.config['port']))
        self.server_sock.listen()

        self.server_thread_info = ThreadBasics(
            thread=threading.Thread(target=self.st_server_thread_fn),
            started_event=threading.Event(),
            stop_event=threading.Event()
        )
        self.server_thread_info.thread.start()
        self.server_thread_info.started_event.wait()

    def stop(self) -> None:
        if self.server_thread_info is not None:
            self.server_thread_info.stop_event.set()
            if self.server_sock is not None:
                self.server_sock.close()    # Will wake up the server thread
           
            server_thread_obj = self.server_thread_info.thread
            server_thread_obj.join(2)
            if server_thread_obj.is_alive():
                self.logger.error("Failed to stop the server. Join timed out")

        self.server_thread_info = None
        self.server_sock = None
        while not self.rx_queue.empty():
            self.rx_queue.get()
        
        for client_id in self.get_client_list():
            self.unregister_client(client_id)


    def process(self) -> None:
        pass


    def available(self) -> bool:
        return not self.rx_queue.empty()

    def recv(self) -> Optional[ClientHandlerMessage]:
        try:
            return self.rx_queue.get_nowait()
        except queue.Empty:
            return None

    def is_connection_active(self, conn_id: str) -> bool:
        """Tells if a client connection is presently functional and alive"""
        with self.registry_lock:
            try:
                sock = self.id2sock_map[conn_id]
            except KeyError:
                return False
        
        if sock.fileno() == -1:
            return False
        
        return True
    
    def get_number_client(self) -> int:
        with self.registry_lock:
            return len(self.id2sock_map)

    @classmethod
    def get_compatible_stream_parser(cls) -> StreamParser:
        return StreamParser(
            mtu=cls.STREAM_MTU,
            interchunk_timeout=cls.STREAM_INTERCHUNK_TIMEOUT,
            use_hash=cls.STREAM_USE_HASH
        )

    @classmethod
    def get_compatible_stream_maker(cls) -> StreamMaker:
        return StreamMaker(
            mtu=cls.STREAM_MTU,
            use_hash=cls.STREAM_USE_HASH
        )

    def st_server_thread_fn(self) -> None:
        """The server thread accepting connections and spawning client threads"""
        if self.server_thread_info is None:
            return
        assert self.server_sock is not None
        selector = selectors.DefaultSelector()
        selector.register(self.server_sock, selectors.EVENT_READ)
        stream_parser = StreamParser(
            mtu=self.STREAM_MTU, 
            interchunk_timeout=self.STREAM_INTERCHUNK_TIMEOUT, 
            use_hash=self.STREAM_USE_HASH
        )

        try:
            self.server_thread_info.started_event.set()
            while not self.server_thread_info.stop_event.is_set():
                events = selector.select()
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
                        selector.register(sock, selectors.EVENT_READ)
                    else:
                        client_socket = cast(socket.socket, key.fileobj)
                        try:
                            client_id = self.sock2id_map[client_socket]
                        except KeyError:
                            self.logger.critical("Received message from unregistered socket")
                            selector.unregister(client_socket)
                            continue

                        try:
                            data = client_socket.recv(self.READ_SIZE)
                        except OSError:
                            # Socket got closed
                            self.unregister_client(client_id)
                            selector.unregister(client_socket)
                            continue
                                                            
                        if not data:
                            # Client is gone
                            self.unregister_client(client_id)
                            try:
                                selector.unregister(client_socket)
                            except KeyError:
                                pass
                        else:
                            self.logger.debug(f"Received {len(data)} bytes from client ID: {client_id}")
                            stream_parser.parse(data)
                            while not stream_parser.queue().empty():
                                datagram = stream_parser.queue().get()
                                try:
                                    obj = json.loads(datagram.decode('utf8'))
                                except json.JSONDecodeError as e:
                                    self.logger.error(f"Received malformed JSON from client {client_id}.")
                                    self.logger.debug(traceback.format_exc())
                                    continue
                                
                                self.rx_queue.put(ClientHandlerMessage(conn_id=client_id, obj=obj))
                                new_data = True
                if new_data and self.rx_event is not None:
                    self.rx_event.set()
                            

        except Exception as e:
            self.logger.error(str(e))
            self.logger.debug(traceback.format_exc())
        finally:
            for conn_id in list(self.id2sock_map.keys()):
                self.unregister_client(conn_id)
            selector.close()

    def get_client_list(self) -> List[str]:
        with self.registry_lock:
            return list(self.id2sock_map.keys())
            
    def st_register_client(self, sock:socket.socket, sockaddr:str) -> str:
        """Register a client. Called by the server thread (st)."""
        conn_id = uuid.uuid4().hex
        with self.registry_lock:
            self.id2sock_map[conn_id] = sock
            self.sock2id_map[sock] = conn_id
        
        self.logger.info(f"New client connected {sockaddr} (ID={conn_id}). {len(self.id2sock_map)} clients total")

        return conn_id
    

    
    def unregister_client(self, conn_id:str) -> None:
        """Close the communication with a client and clear internal entry"""
        with self.registry_lock:
            try:
                sock = self.id2sock_map[conn_id]
            except KeyError:
                return
            
            sockaddr = sock.getsockname()
        
            try:
                sock.close()
            except OSError:
                pass
        
            try:
                del self.id2sock_map[conn_id]
            except KeyError:
                pass

            try:
                del self.sock2id_map[sock]
            except KeyError:
                pass
            nb_client = len(self.id2sock_map)

        self.logger.info(f"Client disconnected {sockaddr} (ID={conn_id}). {nb_client} clients total")
