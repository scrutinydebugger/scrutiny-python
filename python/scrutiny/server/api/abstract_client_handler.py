from abc import ABC, abstractmethod
from typing import Dict, Optional
from dataclasses import dataclass

ClientHandlerConfig = Dict[str, str]

@dataclass
class ClientHandlerMessage:
    conn_id:str
    obj:Dict


class AbstractClientHandler:

    @abstractmethod
    def __init__(self, config:ClientHandlerConfig):
        pass

    @abstractmethod
    def send(self, conn_id:str, msg:Dict)->None:
        pass
    
    @abstractmethod        
    def start(self)->None:
        pass
    
    @abstractmethod        
    def process(self)->None:
        pass
    
    @abstractmethod        
    def available(self)->bool:
        pass
    
    @abstractmethod        
    def recv(self)->Optional[ClientHandlerMessage]:
        pass
    
    @abstractmethod        
    def is_connection_active(self)->bool:
        pass
