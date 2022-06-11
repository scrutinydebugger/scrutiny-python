import logging
import traceback
import threading
import os

from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from .ext2contenttype import EXTENSION_TO_CONTENT_TYPE


class HTTPResponseException(Exception):
    def __init__(self, code, content):
        super().__init__(self, '')
        self.code= code
        self.content = content

def make_server_handler(gui_server_obj):

    class ServerHandler(BaseHTTPRequestHandler):

        def log_message(self, format, *args):
            logger = gui_server_obj.logger
            logger.debug("HTTP Request - (%s) %s" % (args[1], args[0]))

        def do_GET(self):
            try:
                base_folder = gui_server_obj.base_folder
                logger = gui_server_obj.logger
                urlparts = urlparse(self.path)
                file = urlparts.path.strip();
        
                if file.startswith('/'):
                    file = file[1:]
        
                final_file = os.path.join(base_folder, file)
                if os.path.isdir(final_file):
                    final_file = os.path.join(final_file, 'index.html')

                if os.path.commonprefix((os.path.realpath(final_file),base_folder)) != base_folder:
                    raise HTTPResponseException(403, 'Bad URL')

                if not os.path.isfile(final_file):
                    raise HTTPResponseException(404, 'File not found')

                filename, file_extension = os.path.splitext(final_file)

                if file_extension not in EXTENSION_TO_CONTENT_TYPE:
                    raise HTTPResponseException(401, 'Unsupported file format : %s' % file_extension)

                file_content = bytes()
                with open(final_file, 'rb') as f:
                    file_content = f.read()

                self.send_response(200)
                self.send_header("Content-type", EXTENSION_TO_CONTENT_TYPE[file_extension])
                self.end_headers()
                
                self.wfile.write(file_content)

            except HTTPResponseException as e:
                self.send_response(e.code)
                self.end_headers()

                self.wfile.write(bytes(e.content, "utf-8"))

            except Exception as e:
                self.send_response(401)
                self.end_headers()

                self.wfile.write(bytes('Internal error', "utf-8"))
                logger.error('GET response error. %s' % str(e))
                logger.debug(traceback.format_exc())


    return ServerHandler


class ScrutinyGuiHttpServer:

    logger: logging.Logger
    started_event: threading.Event
    request_exit: bool
    thread: Optional[threading.Thread]
    http_server: Optional[HTTPServer]
    base_folder : str

    def __init__(self, base_folder:str):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.started_event = threading.Event()
        self.request_exit = False
        self.thread = None
        self.http_server = None
        self.base_folder = base_folder


    def start(self, port:int) -> None:
        self.logger.debug('Requesting HTTP server to start')
        self.http_server = HTTPServer(('localhost', port), make_server_handler(self))
        self.thread = threading.Thread(target=self.thread_task)
        self.started_event.clear()
        self.thread.start()
        self.started_event.wait()

    def get_port(self) -> int:
        if self.http_server is None:
            return None

        host, port = self.http_server.socket.getsockname()

        return port


    def stop(self) -> None:
        self.logger.debug('Requesting HTTP server to stop')
        if self.http_server is not None:
            self.http_server.shutdown() # Shutdown is thread safe

        self.exit_requested = True
        if self.thread is not None:
            self.thread.join()
        self.thread = None

    def thread_task(self) -> None:
        self.started_event.set()
        self.logger.info('HTTP server started')

        try:
            self.http_server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
        except Exception as e:  
            self.logger.error('HTTP server exited with error. %s' % str(e))
            self.logger.debug(traceback.format_exc())

        self.logger.info('HTTP server stopped')

            

