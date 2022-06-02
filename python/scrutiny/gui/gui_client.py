
import platform
import sys
import logging
import os
from copy import copy
import json
from cefpython3 import cefpython as cef # type: ignore

from os import path

from typing import TypedDict

class GUI_ServerConfig(TypedDict, total=False):
    host:str
    port:int

class GUIConfig(TypedDict, total=False):
    name: str
    server: GUI_ServerConfig


DEFAULT_CONFIG: GUIConfig = {
    'name': 'Scrutiny GUI Client (Default config)',
    'server': {
        'host': "127.0.0.1",
        'port' : 8765
        }
    }

class GUIClient:
    init_ok:bool

    WEBAPP_FOLDER = 'webapp'
    MIN_VERSION = '66.0'
    
    def __init__(self, config_filename:str=None):
        self.init_ok = True
        self.logger = logging.getLogger(self.__class__.__name__)

        ver = cef.GetVersion()
        self.logger.debug("CEF Python %s" % ver["version"])
        self.logger.debug("Chromium %s" % ver["chrome_version"])
        self.logger.debug("CEF %s" % ver["cef_version"])
        self.logger.debug("Python %s %s" % (platform.python_version(), platform.architecture()[0]))

        if cef.__version__ < self.MIN_VERSION:
            self.logger.critical("CEF Python v%s+ required to run the Scrutiny GUI Client" % self.MIN_VERSION)
            self.init_ok = False
        else:
            self.config = copy(DEFAULT_CONFIG)
            self.webapp_fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.WEBAPP_FOLDER)

            if config_filename is not None:
                self.logger.debug('Loading user configuration file: "%s"' % config_filename)
                del self.config['name']  # remove "default config" from name
                with open(config_filename) as f:
                    try:
                        user_cfg = json.loads(f.read())
                        self.config.update(user_cfg)
                    except Exception as e:
                        raise Exception("Invalid configuration JSON. %s" % e)
    def run(self):
        if self.init_ok:
            sys.excepthook = cef.ExceptHook  # To shutdown all CEF processes on error

            settings = {
                "debug": False
            }

            cef.Initialize(settings)
            cef.CreateBrowserSync(url="file:///%s/index.html" % self.webapp_fullpath, window_title="Scrutiny")
            cef.MessageLoop()
            cef.Shutdown()
        else:
            self.logger.critical('Cannot start Scrutiny GUI Client. Exiting.')
