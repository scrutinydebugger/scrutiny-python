# scrutiny

Scrutiny Python module. Contains
 - Server
 - GUI launcher
 - CLI for build toolchain integration
 - Python client lib to script interraction with the server

## Roadmap
Initial Release :
  - Python : https://github.com/scrutinydebugger/scrutiny-python/projects/1
  - Embedded : https://github.com/scrutinydebugger/scrutiny-embedded/projects/1
  - GUI : https://github.com/scrutinydebugger/scrutiny-gui-webapp/projects/1
  - Doc : https://github.com/scrutinydebugger/scrutiny-doc/projects/2

## Getting started

Clone project
```
git clone git@github.com:scrutinydebugger/scrutiny-python.git
cd scrutiny-python
git submodule update --init
```

Launch Server
```
./scripts/with-venv.sh scrutiny launch-server --config config/serial.json
```

Launch GUI
```
./scripts/with-venv.sh scrutiny launch-gui
```
