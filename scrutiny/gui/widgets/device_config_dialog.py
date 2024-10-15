
from qtpy.QtWidgets import QDialog, QWidget, QComboBox, QVBoxLayout, QDialogButtonBox,QFormLayout, QLabel, QLineEdit
from qtpy.QtGui import QIntValidator
from qtpy.QtCore import Qt
from scrutiny import sdk
from scrutiny.gui.widgets.validable_line_edit import ValidableLineEdit
from scrutiny.gui.tools.validators import IpPortValidator, NotEmptyValidator
import abc
from typing import Optional, Dict, Union, Type, cast
import logging
import traceback

SUPPORTED_CONFIGS=Optional[Union[sdk.UDPLinkConfig, sdk.TCPLinkConfig, sdk.SerialLinkConfig, sdk.RTTLinkConfig]]

class BaseConfigPane(QWidget):
    def get_config(self) -> Optional[sdk.BaseLinkConfig]:
        raise NotImplementedError("abstract method")

    def load_config(self, config:Optional[sdk.BaseLinkConfig]) -> None:
        raise NotImplementedError("abstract method")
    
    def visual_validation(self) -> None:
        pass

    @classmethod
    def make_config_valid(self, config:Optional[sdk.BaseLinkConfig]) -> Optional[sdk.BaseLinkConfig]:
        return config


class NoConfigPane(BaseConfigPane):
    def get_config(self) -> Optional[sdk.BaseLinkConfig]:
        return None

    def load_config(self, config:Optional[sdk.BaseLinkConfig]) -> None:
        self.make_config_valid(config)

class IPConfigPane(BaseConfigPane):
    _hostname_textbox: ValidableLineEdit
    _port_textbox: ValidableLineEdit

    def __init__(self, parent:Optional[QWidget]=None) -> None:
        super().__init__(parent)

        form_layout = QFormLayout(self)
        form_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        hostname_label = QLabel("Hostname: ")
        port_label = QLabel("Port: ")
        self._hostname_textbox = ValidableLineEdit(soft_validator=NotEmptyValidator())
        self._port_textbox = ValidableLineEdit(hard_validator=QIntValidator(0,0xFFFF), soft_validator=IpPortValidator())

        # Make sure the red background disappear when we type (fixing the invalid content)
        self._hostname_textbox.textChanged.connect(self._hostname_textbox.validate_expect_not_wrong)
        self._port_textbox.textChanged.connect(self._port_textbox.validate_expect_not_wrong)
        
        form_layout.addRow(hostname_label, self._hostname_textbox)
        form_layout.addRow(port_label, self._port_textbox)
    
    def get_port(self) -> Optional[int]:
        port_txt = self._port_textbox.text()
        state, _, _ = IpPortValidator().validate(port_txt, 0)
        if state == IpPortValidator.State.Acceptable:
            return int(port_txt)    # Should not fail
        return None
    
    def set_port(self, port:int) -> None:
        port_txt = str(port)
        state, _, _ = IpPortValidator().validate(port_txt, 0)
        if state != IpPortValidator.State.Acceptable:
            raise ValueError(f"Invalid port number: {port}")
        self._port_textbox.setText(port_txt)


    def get_hostname(self) -> str:
        return self._hostname_textbox.text()
    
    def set_hostname(self, hostname:str) -> None:
        self._hostname_textbox.setText(hostname)

    def visual_validation(self) -> None:
        self._port_textbox.validate_expect_valid()
        self._hostname_textbox.validate_expect_valid()

class TCPConfigPane(IPConfigPane):
    def get_config(self) -> Optional[sdk.TCPLinkConfig]:
        port = self.get_port()
        if port is None:
            return None

        return sdk.TCPLinkConfig(
            host = self.get_hostname(),
            port = port,
        )

    def load_config(self, config:Optional[sdk.BaseLinkConfig]) -> None:
        config = self.make_config_valid(config)
        assert isinstance(config, sdk.TCPLinkConfig)
        self.set_hostname(config.host)
        self.set_port(config.port)

    @classmethod
    def make_config_valid(self, config:Optional[sdk.BaseLinkConfig]) -> Optional[sdk.BaseLinkConfig]:
        assert isinstance(config, sdk.TCPLinkConfig) 
        port = max(min(config.port, 0xFFFF), 0)
        hostname = config.host
        if len(hostname) == 0:
            hostname = 'localhost'
        
        return sdk.TCPLinkConfig(
            host = hostname,
            port=port
        )

class UDPConfigPane(IPConfigPane):
    def get_config(self) -> Optional[sdk.UDPLinkConfig]:
        port = self.get_port()
        if port is None:
            return None
        
        return sdk.UDPLinkConfig(
            host = self.get_hostname(),
            port = port,
        )

    def load_config(self, config:Optional[sdk.BaseLinkConfig]) -> None:
        config = self.make_config_valid(config)
        assert isinstance(config, sdk.UDPLinkConfig)
        self.set_hostname(config.host)
        self.set_port(config.port)

    @classmethod
    def make_config_valid(self, config:Optional[sdk.BaseLinkConfig]) -> Optional[sdk.BaseLinkConfig]:
        assert isinstance(config, sdk.UDPLinkConfig) 
        port = max(min(config.port, 0xFFFF), 0)
        hostname = config.host
        if len(hostname) == 0:
            hostname = 'localhost'
        
        return sdk.UDPLinkConfig(
            host = hostname,
            port=port
        )


class SerialConfigPane(BaseConfigPane):
    _port_name_textbox:ValidableLineEdit
    _baudrate_textbox:ValidableLineEdit
    _stopbits_combo_box:QComboBox
    _databits_combo_box:QComboBox
    _parity_combo_box:QComboBox


    def __init__(self, parent:Optional[QWidget]=None) -> None:
        super().__init__(parent)

        layout = QFormLayout(self)
        self._port_name_textbox = ValidableLineEdit(soft_validator=NotEmptyValidator())
        self._baudrate_textbox = ValidableLineEdit(
            hard_validator=QIntValidator(0,0x7FFFFFFF),
            soft_validator=NotEmptyValidator()
        )
        self._stopbits_combo_box = QComboBox()
        self._stopbits_combo_box.addItem("1", sdk.SerialLinkConfig.StopBits.ONE)
        self._stopbits_combo_box.addItem("1.5", sdk.SerialLinkConfig.StopBits.ONE_POINT_FIVE)
        self._stopbits_combo_box.addItem("2", sdk.SerialLinkConfig.StopBits.TWO)
        self._stopbits_combo_box.setCurrentIndex(self._stopbits_combo_box.findData(sdk.SerialLinkConfig.StopBits.ONE))

        self._databits_combo_box = QComboBox()
        self._databits_combo_box.addItem("5", sdk.SerialLinkConfig.DataBits.FIVE)
        self._databits_combo_box.addItem("6", sdk.SerialLinkConfig.DataBits.SIX)
        self._databits_combo_box.addItem("7", sdk.SerialLinkConfig.DataBits.SEVEN)
        self._databits_combo_box.addItem("8", sdk.SerialLinkConfig.DataBits.EIGHT)
        self._databits_combo_box.setCurrentIndex(self._databits_combo_box.findData(sdk.SerialLinkConfig.DataBits.EIGHT))

        self._parity_combo_box = QComboBox()
        self._parity_combo_box.addItem("None", sdk.SerialLinkConfig.Parity.NONE)
        self._parity_combo_box.addItem("Even", sdk.SerialLinkConfig.Parity.EVEN)
        self._parity_combo_box.addItem("Odd", sdk.SerialLinkConfig.Parity.ODD)
        self._parity_combo_box.addItem("Mark", sdk.SerialLinkConfig.Parity.MARK)
        self._parity_combo_box.addItem("Space", sdk.SerialLinkConfig.Parity.SPACE)
        self._parity_combo_box.setCurrentIndex(self._parity_combo_box.findData(sdk.SerialLinkConfig.Parity.NONE))

        layout.addRow(QLabel("Port: "), self._port_name_textbox)
        layout.addRow(QLabel("Baudrate: "), self._baudrate_textbox)
        layout.addRow(QLabel("Stop bits: "), self._stopbits_combo_box)
        layout.addRow(QLabel("Data bits: "), self._databits_combo_box)
        layout.addRow(QLabel("Parity: "), self._parity_combo_box)

        # Make sure the red background disappear when we type (fixing the invalid content)
        self._port_name_textbox.textChanged.connect(self._port_name_textbox.validate_expect_not_wrong)
        self._baudrate_textbox.textChanged.connect(self._baudrate_textbox.validate_expect_not_wrong)


    def get_config(self) -> Optional[sdk.SerialLinkConfig]:
        port = self._port_name_textbox.text()
        baudrate_str = self._baudrate_textbox.text()
        stopbits = cast(sdk.SerialLinkConfig.StopBits, self._stopbits_combo_box.currentData())
        databits = cast(sdk.SerialLinkConfig.DataBits, self._databits_combo_box.currentData())
        parity = cast(sdk.SerialLinkConfig.Parity, self._parity_combo_box.currentData())
        
        if len(port) == 0:
            return None
        
        try : 
            baudrate = int(baudrate_str)
        except Exception:
            return None
        
        if baudrate < 0:
            return None

        return sdk.SerialLinkConfig(
            port = port,
            baudrate = baudrate,
            stopbits = stopbits,
            databits = databits,
            parity = parity
        )

    def load_config(self, config:Optional[sdk.BaseLinkConfig]) -> None:
        config = self.make_config_valid(config)
        assert isinstance(config, sdk.SerialLinkConfig)

        self._port_name_textbox.setText(config.port)
        self._baudrate_textbox.setText(str(config.baudrate))
        self._stopbits_combo_box.setCurrentIndex(self._stopbits_combo_box.findData(config.stopbits))
        self._databits_combo_box.setCurrentIndex(self._databits_combo_box.findData(config.databits))
        self._parity_combo_box.setCurrentIndex(self._parity_combo_box.findData(config.parity))
        
    @classmethod
    def make_config_valid(self, config:Optional[sdk.BaseLinkConfig]) -> Optional[sdk.BaseLinkConfig]:
        assert isinstance(config, sdk.SerialLinkConfig)
        return sdk.SerialLinkConfig(
            port = "<port>" if len(config.port) else config.port,
            baudrate = max(config.baudrate, 1),
            stopbits = config.stopbits,
            databits = config.databits,
            parity = config.parity
        )
    
    def visual_validation(self) -> None:
        self._port_name_textbox.validate_expect_valid()
        self._baudrate_textbox.validate_expect_valid()


class DeviceConfigDialog(QDialog):

    CONFIG_TYPE_TO_WIDGET:Dict[sdk.DeviceLinkType, Type[BaseConfigPane]] = {
        sdk.DeviceLinkType.NA: NoConfigPane,
        sdk.DeviceLinkType.TCP: TCPConfigPane,
        sdk.DeviceLinkType.UDP: UDPConfigPane,
        sdk.DeviceLinkType.Serial: SerialConfigPane
    }

    _link_type_combo_box:QComboBox
    _config_container:QWidget
    _configs:Dict[sdk.DeviceLinkType, SUPPORTED_CONFIGS]
    _active_pane:Optional[BaseConfigPane]

    def __init__(self, parent:Optional[QWidget]=None) -> None:
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        vlayout = QVBoxLayout(self)
        self._link_type_combo_box = QComboBox()
        self._link_type_combo_box.addItem("None", sdk.DeviceLinkType.NA)
        self._link_type_combo_box.addItem("Serial", sdk.DeviceLinkType.Serial)
        self._link_type_combo_box.addItem("UDP/IP", sdk.DeviceLinkType.UDP)
        self._link_type_combo_box.addItem("TCP/IP", sdk.DeviceLinkType.TCP)
        self._link_type_combo_box.addItem("JLink RTT", sdk.DeviceLinkType.RTT)

        self._config_container = QWidget()
        self._config_container.setLayout(QVBoxLayout())
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._btn_ok_click)
        buttons.rejected.connect(self._btn_cancel_click)
        
        vlayout.addWidget(self._link_type_combo_box)
        vlayout.addWidget(self._config_container)
        vlayout.addWidget(buttons)

        self._configs = {}

        self._configs[sdk.DeviceLinkType.NA] = None
        self._configs[sdk.DeviceLinkType.UDP] = sdk.UDPLinkConfig(host="localhost", port=8765)
        self._configs[sdk.DeviceLinkType.TCP] = sdk.TCPLinkConfig(host="localhost", port=8765)
        self._configs[sdk.DeviceLinkType.Serial] = sdk.SerialLinkConfig(port="<port>", baudrate=115200) # Rest has default values

        self._link_type_combo_box.currentIndexChanged.connect(self._combobox_changed)
        self._active_pane = None
        self.swap_config_pane(sdk.DeviceLinkType.NA)
        
    def set_config(self, link_type:sdk.DeviceLinkType, config:SUPPORTED_CONFIGS ) -> None:
        if link_type not in self._configs:
            raise ValueError("Unsupported config type")
        
        try:
            config = cast(SUPPORTED_CONFIGS, self.CONFIG_TYPE_TO_WIDGET[link_type].make_config_valid(config))
            self._configs[link_type] = config
        except Exception as e:
            self.logger.warning(f"Tried to load an invalid config. {e}")
            self.logger.debug(traceback.format_exc())
    
    def _get_selected_link_type(self) -> sdk.DeviceLinkType:
        return cast(sdk.DeviceLinkType, self._link_type_combo_box.currentData())
        
    def swap_config_pane(self, link_type:sdk.DeviceLinkType) -> None:
        combobox_index = self._link_type_combo_box.findData(link_type)
        if combobox_index < 0:
            raise ValueError(f"Given link type not in the combobox {link_type}")
        self._link_type_combo_box.setCurrentIndex(combobox_index)

    def _combobox_changed(self) -> None:
        link_type = self._get_selected_link_type()
        self._rebuild_config_layout(link_type)

    def _rebuild_config_layout(self, link_type:sdk.DeviceLinkType) -> None:
        config = self._configs[link_type]
        layout = self._config_container.layout()

        for pane in self._config_container.children():
            if isinstance(pane, BaseConfigPane):
                layout.removeWidget(pane)

        self._active_pane = self.CONFIG_TYPE_TO_WIDGET[link_type]()
        layout.addWidget(self._active_pane)
        self._config_container

        try:
            self._active_pane.make_config_valid(config)
            self._active_pane.load_config(config)
        except Exception as e:
            self.logger.warning(f"Tried to apply an invalid config to the window. {e}")
            self.logger.debug(traceback.format_exc())

    def _btn_ok_click(self) -> None:
        assert self._active_pane is not None
        link_type = self._get_selected_link_type()
        config = self._active_pane.get_config()
        self._active_pane.visual_validation()
        # if config is None, it is invalid. Don't close and expect the user to fix
        if config is not None:
            self._configs[link_type] = cast(SUPPORTED_CONFIGS, config)
            self.close()

    def _btn_cancel_click(self) -> None:
        assert self._active_pane is not None
        # Reload to the UI the config that is saved
        config = self._configs[self._get_selected_link_type()]
        self._active_pane.load_config(config)   # Should not raise. This config was there before.
        self.close()
