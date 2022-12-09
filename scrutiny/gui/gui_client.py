#    gui_client.py
#        Represent the GUI application. Allows to launch through Chromium Embedded Framework
#        or in a web browser with local server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import platform
import sys
import os
import logging
import enum
from copy import copy
import json
import traceback
import time
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from base64 import b64encode
import json

from typing import TypedDict, Optional
from .scrutiny_gui_http_server import ScrutinyGuiHttpServer


class GUI_ServerConfig(TypedDict, total=False):
    host: str
    port: int


class LocalWebServerConfig(TypedDict, total=False):
    port: int


class GUIConfig(TypedDict, total=False):
    name: str
    server: GUI_ServerConfig
    local_webserver: LocalWebServerConfig


DEFAULT_CONFIG: GUIConfig = {
    'name': 'Scrutiny GUI Client (Default config)',
    'server': {
        'host': "127.0.0.1",
        'port': 8765
    },
    'local_webserver': {
        'port': 0
    }
}


class LoadHandler(object):
    def OnLoadingStateChange(self, browser, is_loading, **_):
        if not is_loading:
            # Loading is complete. DOM is ready.
            pass


class LaunchMethod(enum.Enum):
    CEF = enum.auto()
    WEB_BROWSER = enum.auto()


class GUIClient:

    CEF_MIN_VERSION: str = '66.0'

    launch_method: LaunchMethod
    logger: logging.Logger
    http_server_port: int
    config: GUIConfig
    webapp_path: str
    gui_server: ScrutinyGuiHttpServer

    def __init__(self, webapp_path: str, config_filename: Optional[str] = None, launch_method: LaunchMethod = LaunchMethod.WEB_BROWSER, http_server_port: int = 0):
        self.launch_method = launch_method
        self.logger = logging.getLogger(self.__class__.__name__)
        self.http_server_port = http_server_port

        self.config = copy(DEFAULT_CONFIG)
        self.webapp_path = webapp_path
        if not os.path.isdir(self.webapp_path):
            raise FileNotFoundError("%s is not a folder" % self.webapp_path)

        if config_filename is not None:
            self.logger.debug('Loading user configuration file: "%s"' % config_filename)
            del self.config['name']  # remove "default config" from name
            with open(config_filename) as f:
                try:
                    user_cfg = json.loads(f.read())
                    self.config.update(user_cfg)
                except Exception as e:
                    raise Exception("Invalid configuration JSON. %s" % e)

    def run(self) -> None:
        self.gui_server = ScrutinyGuiHttpServer(base_folder=self.webapp_path)
        self.gui_server.start(port=self.http_server_port)
        self.http_server_port = self.gui_server.get_port()

        # Launch the client
        url = 'http://localhost:%d' % self.http_server_port
        config_str = b64encode(json.dumps(self.config).encode('utf8')).decode('ascii')
        # Add config to url as we don't have CEF hooks to communicate with the webapp
        url_parts = list(urlparse(url))
        query = dict(parse_qsl(url_parts[4]))
        query.update({'config': config_str})    # Add config

        url_parts[4] = urlencode(query)
        url = urlunparse(url_parts)

        try:
            if self.launch_method == LaunchMethod.WEB_BROWSER:
                self.try_launch_webbrowser(url)
            elif self.launch_method == LaunchMethod.CEF:
                self.try_launch_cef(url)
            else:
                raise NotImplementedError('Unknown launch method')
        except Exception as e:
            self.gui_server.stop()
            raise e

        self.gui_server.stop()

    def try_launch_webbrowser(self, url: str):
        import webbrowser
        webbrowser.open_new_tab(url)

        while True:
            try:
                time.sleep(0.5)  # Nothing to do here
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(str(e))
                self.logger.debug(traceback.format_exc())

    def try_launch_cef(self, url: str):
        from cefpython3 import cefpython as cef  # type: ignore

        ver = cef.GetVersion()
        self.logger.debug("CEF Python %s" % ver["version"])
        self.logger.debug("Chromium %s" % ver["chrome_version"])
        self.logger.debug("CEF %s" % ver["cef_version"])
        self.logger.debug("Python %s %s" % (platform.python_version(), platform.architecture()[0]))

        if cef.__version__ < self.CEF_MIN_VERSION:
            raise NotImplementedError("CEF Python v%s+ required to run the Scrutiny GUI Client" % self.MIN_VERSION)

        sys.excepthook = cef.ExceptHook  # To shutdown all CEF processes on error

        app_settings = {
            "debug": False
        }

        browser_settings = {
            'web_security_disabled': True  # We need to load files through ajax
        }

        cef.Initialize(app_settings)
        browser = cef.CreateBrowserSync(navigateUrl=url, window_title='Scrutiny', settings=browser_settings)

        # Configure browser
        browser.SetClientHandler(LoadHandler())
        bindings = cef.JavascriptBindings(bindToFrames=False, bindToPopups=False)
        bindings.SetProperty("config_from_python", self.config)
        browser.SetJavascriptBindings(bindings)

        # Launch everything
        cef.MessageLoop()
        cef.Shutdown()
