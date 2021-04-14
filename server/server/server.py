from api import API
import time

config= {
    'host' : 'localhost',
    'port' : 8765,
    'name' : 'Dev server'
}

if __name__ == '__main__':
    theapi = API(config)

    theapi.start_listening()

    try:
        while True:
            theapi.process()
            time.sleep(0.1)
    except:
        theapi.close()
        raise
        
