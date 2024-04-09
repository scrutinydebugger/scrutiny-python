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
scrutiny launch-server --config config/serial.json
```

## Getting started - Developper

Install

```
git clone git@github.com:scrutinydebugger/scrutiny-python.git
cd scrutiny-python
git submodule update --init
```

Launch Server
```
./scripts/with-venv.sh scrutiny launch-server --config config/serial.json
```

## More info

Check https://scrutinydebugger.com
