
import platform
import sys
import logging
import os
import enum
from copy import copy
import json
import traceback
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
        },
    'local_webserver': {
            'port' : 8081
        }
    }

class LoadHandler(object):
    def OnLoadingStateChange(self, browser, is_loading, **_):
        if not is_loading:
            # Loading is complete. DOM is ready.
           pass

class LaunchMethod(enum.Enum):
    NONE = enum.auto()
    CEF = enum.auto()
    WEB_BROWSER = enum.auto()


class GUIClient:
    launch_method:LaunchMethod

    WEBAPP_FOLDER = 'webapp/build/'
    CEF_MIN_VERSION = '66.0'
    
    def __init__(self, config_filename:str=None, launch_method:LaunchMethod=LaunchMethod.NONE):
        self.launch_method = launch_method
        self.logger = logging.getLogger(self.__class__.__name__)

        self.config = copy(DEFAULT_CONFIG)
        self.webapp_fullpath = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), self.WEBAPP_FOLDER))
        self.webapp_entry_point_absolute = "file:///%s" % os.path.join(self.webapp_fullpath, 'index.html')
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
        launch_method_not_set = (self.launch_method == LaunchMethod.NONE)

        if self.launch_method in [LaunchMethod.NONE, LaunchMethod.CEF]:
            try:
                self.launch_method = LaunchMethod.CEF
                self.try_launch_cef()
            except Exception as e:
                self.logger.warning('Cannot use Chromium Embedded Framework to launch the GUI. %s' % str(e))
                self.logger.debug(traceback.format_exc())
                
                if launch_method_not_set:
                    self.launch_method = LaunchMethod.NONE
                else:
                    raise e

        if self.launch_method in [LaunchMethod.NONE, LaunchMethod.WEB_BROWSER]:
            try:
                self.launch_method = LaunchMethod.WEB_BROWSER
                self.try_launch_webbrowser()
            except Exception as e:
                self.logger.warning('Cannot use webbrowser module to launch the GUI. %s' % str(e))
                self.logger.debug(traceback.format_exc())
                if launch_method_not_set:
                    self.launch_method = LaunchMethod.NONE
                else:
                    raise e

        if self.launch_method == LaunchMethod.NONE:
            raise Exception('Cannot launch Scrutiny GUI. Exiting')

    def try_launch_webbrowser(self):
        import webbrowser
        from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
        import json

        config_str = json.dumps(self.config).encode('utf8')
        # Add config to url as we don't have CEF hooks to communicate with the webapp
        url_parts = list(urlparse(self.webapp_entry_point_absolute))
        query = dict(parse_qsl(url_parts[4]))
        query.update({'config' : config_str})    # Add config
        url_parts[4] = urlencode(query)
        url = urlunparse(url_parts)    

        #fixme : config is lost with the file protocol : 
        # https://stackoverflow.com/questions/72553727/python-webbrowser-module-and-query-string-with-file-protocol
        webbrowser.open_new_tab(url)

    def try_launch_cef(self):
        from cefpython3 import cefpython as cef # type: ignore
        
        ver = cef.GetVersion()
        self.logger.debug("CEF Python %s" % ver["version"])
        self.logger.debug("Chromium %s" % ver["chrome_version"])
        self.logger.debug("CEF %s" % ver["cef_version"])
        self.logger.debug("Python %s %s" % (platform.python_version(), platform.architecture()[0]))

        if cef.__version__ < self.CEF_MIN_VERSION:
            raise NotImplementedError("CEF Python v%s+ required to run the Scrutiny GUI Client" % self.MIN_VERSION)

        sys.excepthook = cef.ExceptHook  # To shutdown all CEF processes on error

        settings = {
            "debug": False
        }
        
        cef.Initialize(settings)
        browser = cef.CreateBrowserSync(navigateUrl=self.webapp_entry_point_absolute, window_title='Scrutiny')
        
        # Configure browser
        browser.SetClientHandler(LoadHandler())
        bindings = cef.JavascriptBindings(bindToFrames=False, bindToPopups=False)
        bindings.SetProperty("config_from_python", self.config)
        browser.SetJavascriptBindings(bindings)
        
        # Launch everything
        cef.MessageLoop()
        cef.Shutdown()


        
