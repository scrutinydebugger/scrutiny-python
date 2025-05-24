from scrutiny.cli import CLI
import sys
import os

def scrutiny_server() -> None:
    cli = CLI(os.getcwd())
    code = cli.run(['server'] + sys.argv[1:])
    sys.exit(code)

if __name__ == '__main__':
    scrutiny_server()
