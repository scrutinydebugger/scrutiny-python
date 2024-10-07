from qtpy.QtWidgets import QStatusBar, QWidget, QLabel
from scrutiny.gui.core.server_manager import ServerManager
from scrutiny.sdk import ServerState


class StatusBar(QStatusBar):
    _server_manager:ServerManager
    _server_status_label:QLabel
    _device_status_label:QLabel
    _sfd_status_label:QLabel
    _datalogger_status_label:QLabel
    
    def __init__(self, parent:QWidget, server_manager:ServerManager) -> None:
        super().__init__(parent)
        self._server_manager=server_manager

        self._server_status_label = QLabel("Disconnected")
        self._device_status_label = QLabel("N/A")
        self._sfd_status_label = QLabel("-")
        self._datalogger_status_label = QLabel("N/A")
        self.addWidget(QLabel("Server: "))
        self.addWidget(self._server_status_label)
        self.addWidget(QLabel("Device: "))
        self.addWidget(self._device_status_label)
        self.addWidget(QLabel("SFD: "))
        self.addWidget(self._sfd_status_label)
        self.addWidget(QLabel("Datalogger: "))
        self.addWidget(self._datalogger_status_label)

        self._server_status_label.setMinimumWidth(32)
        self._device_status_label.setMinimumWidth(32)
        self._sfd_status_label.setMinimumWidth(32)
        self._datalogger_status_label.setMinimumWidth(32)

        self._server_manager.signals.server_connected.connect(self.update)
        self._server_manager.signals.server_disconnected.connect(self.update)
        self._server_manager.signals.device_ready.connect(self.update)
        self._server_manager.signals.device_disconnected.connect(self.update)
        self._server_manager.signals.datalogging_state_changed.connect(self.update)
        self._server_manager.signals.sfd_loaded.connect(self.update)
        self._server_manager.signals.sfd_unloaded.connect(self.update)


    def update(self) -> None:
        server_state = self._server_manager.get_server_state()
        self._server_status_label.setText(server_state.name)

        server_info = self._server_manager.get_server_info()
        if server_info is None:
            self._device_status_label.setText("N/A")
            self._sfd_status_label.setText("-")
            self._datalogger_status_label.setText("N/A")
        else:
            self._device_status_label.setText(server_info.device_comm_state.name)
            if server_info.sfd is None:
                self._sfd_status_label.setText("-")
            else:
                project_name = "Unnamed project"
                if server_info.sfd.metadata is not None:
                    if server_info.sfd.metadata.project_name is not None:
                        project_name = server_info.sfd.metadata.project_name
                        if server_info.sfd.metadata.version is not None:
                            project_name += ' V' + server_info.sfd.metadata.version

                sfd_str = f"Loaded ({project_name})"
                self._sfd_status_label.setText(sfd_str)
            
            datalogging_str = server_info.datalogging.state.name
            if server_info.datalogging.completion_ratio is not None:
                percent = server_info.datalogging.completion_ratio*100
                datalogging_str += f" {percent:0.1f}%"
            self._datalogger_status_label.setText(datalogging_str)
