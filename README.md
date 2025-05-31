# Scrutiny main module


Scrutiny main module. Contains
 - Server
 - QT GUI 
 - CLI for build toolchain integration
 - Python SDK


## Getting started - User

Install 

```
pip install scrutinydebugger
```

Launch Server
```
scrutiny server [--config <config>.json] [--port <port>]
```

Launch GUI
```
scrutiny gui [--start-local-server] [--auto-connect]
```

## Getting started - Developper 

Install

```
git clone ssh://git@github.com/scrutinydebugger/scrutiny-main.git
python -m venv venv                 # Creates a virtual environment
source venv/Scripts/activate        # Activates the virutal environment (Windows path)
source venv/bin/activate            # Activates the virutal environment (Linux path)
pip install -e scrutiny-main[dev]   # Installs Scrutiny in development mode

python -m scrutiny server [--config <config>.json]          # Launches scrutiny server
python -m scrutiny gui --start-local-server --auto-connect  # Launches the GUI with a local server
python -m scrutiny runtest                                  # Launches the unit tests
```

## More info

Check https://scrutinydebugger.com
