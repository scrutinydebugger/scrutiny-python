# Scrutiny Python module


Scrutiny Python module. Contains
 - Server
 - GUI launcher
 - CLI for build toolchain integration
 - Python SDK


## Getting started - User

Install 

```
pip install scrutinydebugger
```

Launch Server
```
scrutiny server --config config/serial.json
```

Launch GUI (under development)
```
scrutiny gui
```

## Getting started - Developper 

Install

```
git clone git@github.com:scrutinydebugger/scrutiny-python.git
```

Launch Server (Linux)
```
./scripts/with-venv.sh scrutiny server --config config/serial.json
```

Launch Server (Windows):

No automation available. Dependencies can be installed manually inside a venv then the following command can be used:

```
python -m scrutiny server --config config/serial.json
```

## More info

Check https://scrutinydebugger.com
