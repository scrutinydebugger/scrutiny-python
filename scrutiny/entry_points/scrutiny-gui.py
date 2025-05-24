from scrutiny.cli import CLI
import sys
import os

def scrutiny_gui_with_server() -> None:
    cli = CLI(os.getcwd())
    code = cli.run(['gui', '--start-local-server', '--auto-connect'] + sys.argv[1:])
    sys.exit(code)

if __name__ == '__main__':
    scrutiny_gui_with_server()
