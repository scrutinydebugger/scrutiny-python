#    abstract_client_handler.py
#        Base class for all API client handlers
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from abc import abstractmethod
from typing import Dict, Optional, Union
from dataclasses import dataclass
import threading

import scrutiny.server.api.typing as api_typing

ClientHandlerConfig = Dict[str, str]


@dataclass
class ClientHandlerMessage:
    conn_id: str
    obj: Union[api_typing.C2SMessage, api_typing.S2CMessage]


class AbstractClientHandler:
    
    @dataclass
    class Statistics:
        client_count:int
        output_datarate_byte_per_sec:float
        input_datarate_byte_per_sec:float
        msg_received:int
        msg_sent:int


    @abstractmethod
    def __init__(self, config: ClientHandlerConfig, rx_event:Optional[threading.Event]=None):
        pass

    @abstractmethod
    def send(self, msg: ClientHandlerMessage) -> None:
        pass

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def process(self) -> None:
        pass

    @abstractmethod
    def available(self) -> bool:
        pass

    @abstractmethod
    def recv(self) -> Optional[ClientHandlerMessage]:
        pass

    @abstractmethod
    def is_connection_active(self, conn_id: str) -> bool:
        pass

    def get_stats(self) -> Statistics:
        return self.Statistics(
            client_count=0,
            input_datarate_byte_per_sec=0,
            msg_received=0,
            msg_sent=0,
            output_datarate_byte_per_sec=0
        )
