import sys
from api import API
from datastore import Datastore
import time
import argparse

import logging

def str_to_loglevel(s):
    s = s.lower().strip()
    if s == "critical":
        return logging.CRITICAL
    if s == "error":
        return logging.ERROR
    elif s == "warning":
        return logging.WARNING
    elif s == "info":
        return logging.INFO
    elif s == "debug":
        return logging.DEBUG
    else:
        raise ValueError('Unknown log level %s' % s)


def parse_cmd_line():
    options = {
    }

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="default_config", help="Configuration file to load")
    parser.add_argument("--log", default=logging.ERROR,  type=str_to_loglevel, help="Verbosity level")
    parser.add_argument('--log_websockets', default=logging.ERROR, type=str_to_loglevel, help="Verbosity level of websockets module")

    args, unknown = parser.parse_known_args()

    options['config'] = __import__(args.config)
    options['log_websockets'] = args.log_websockets
    options['log_level'] = args.log

    return options

def configure_logging(options):
    logging.basicConfig(stream=sys.stderr, level=options['log_level'])

    websockets_loggers = ['websockets.server', 'websockets.protocol', 'asyncio']
    for name in websockets_loggers:
        logger = logging.getLogger(name)
        logger.setLevel(options['log_websockets'])

if __name__ == '__main__':
    options = parse_cmd_line()
    configure_logging(options)



    ds = Datastore()
    theapi = API(options['config'].APIConfig, ds)
    theapi.start_listening()

    try:
        while True:
            theapi.process()
            time.sleep(0.05)
    except:
        theapi.close()
        raise
        


