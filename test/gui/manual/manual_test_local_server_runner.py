
if __name__ != '__main__' : 
    raise RuntimeError("This script is expected to run from the command line")

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from manual_test_base import make_manual_test_app
app = make_manual_test_app()

from scrutiny.gui.dialogs.local_server_manager_dialog import LocalServerManagerDialog
from scrutiny.gui.core.local_server_runner import LocalServerRunner

runner = LocalServerRunner()
dialog = LocalServerManagerDialog(None, runner)
dialog.show()

app.aboutToQuit.connect(runner.stop)

sys.exit(app.exec())
