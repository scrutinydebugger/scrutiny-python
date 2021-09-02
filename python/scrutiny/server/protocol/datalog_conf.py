from enum import Enum
from scrutiny.core import VariableType

class DatalogConfiguration:
    __slots__ = '_destination', '_sample_rate', '_decimation', '_trigger', 'watches'

    class TriggerCondition(Enum):
        EQUAL= 0
        LESS_THAN = 1
        GREATER_THAN = 2
        LESS_OR_EQUAL_THAN = 3
        GREATER_OR_EQUAL_THAN = 4
        CHANGE = 5
        CHANGE_GREATER = 6
        CHANGE_LESS = 7

    class Operand:
        class Type(Enum):
            CONST = 1
            WATCH = 2

        def get_type_id(self):
            return self.type.value

    class ConstOperand(Operand):
        def __init__(self, value):
            self.value = value
            self.type = self.Type.CONST

    class WatchOperand(Operand):
        def __init__(self, address, length, interpret_as):
            self.address = address
            self.length = length
            self.interpret_as = VariableType(interpret_as)
            self.type = self.Type.WATCH

    class Watch:
        __slots__ = 'address', 'length'
        def __init__(self, address, length):
            self.address = address
            self.length = length

    class Trigger:
        __slots__ = '_condition', '_operand1', '_operand2'

        @property
        def condition(self):
            return self._condition

        @condition.setter
        def condition(self, val):
            if not isinstance(val,  DatalogConfiguration.TriggerCondition):
                raise ValueError('Trigger condition must be an instance of TriggerCondition')
            self._condition = val
       
        @property
        def operand1(self):
            return self._operand1

        @operand1.setter
        def operand1(self, val):
            if not isinstance(val,  DatalogConfiguration.Operand):
                raise ValueError('operand1 must be an instance of TriggerCondition.Operand')
            self._operand1 = val

        @property
        def operand2(self):
            return self._operand2

        @operand2.setter
        def operand2(self, val):
            if not isinstance(val,  DatalogConfiguration.Operand):
                raise ValueError('operand2 must be an instance of TriggerCondition.Operand')
            self._operand2 = val

    def __init__(self):
        self.watches = []
        self._trigger = self.Trigger()

    def add_watch(self, address, length):
        self.watches.append(self.Watch(address, length))



    @property
    def destination(self):
        return self._destination

    @destination.setter
    def destination(self, val):
        if not isinstance(val, int):
            raise ValueError('destination must be an integer')
        self._destination = val

    @property
    def sample_rate(self):
        return self._sample_rate

    @sample_rate.setter
    def sample_rate(self, val):
        if not isinstance(val, (int, float)):
            raise ValueError('sample_rate must be a a numeric value')

        if val <= 0:
            raise ValueError('sample_rate must be a positive value')

        self._sample_rate = val

    @property
    def decimation(self):
        return self._decimation

    @decimation.setter
    def decimation(self, val):
        if not isinstance(val, int):
            raise ValueError('decimation must be an integer')

        if val < 1:
            raise ValueError('decimation must be an integer greater than or equal to 1')

        self._decimation = val


    @property
    def trigger(self):
        return self._trigger

    @trigger.setter
    def trigger(self, val):
        if not isinstance(val, self.Trigger):
            raise ValueError('trigger must be an instance of DatalogConfiguration.Trigger')

        self._trigger = val

class DatalogTarget:
    class Type(Enum):
        RAM = 0
        ROM = 1
        EXTERNAL = 2

    def __init__(self, target_id, target_type, name):
        self.target_id = target_id
        self.target_type = target_type
        self.name = name

    @property
    def target_id(self):
        return self._target_id

    @target_id.setter
    def target_id(self, val):
        if not isinstance(val,  int):
            raise ValueError('Target ID must be an integer')

        if val < 0 or val > 0xFF:
            raise ValueError('Target ID must be a one byte positive integer')
            
        self._target_id = val


    @property
    def target_type(self):
        return self._target_type

    @target_type.setter
    def target_type(self, val):
        if not isinstance(val,  self.Type):
            raise ValueError('Target type must be an instance of DatalogTarget.Type')
            
        self._target_type = val

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, val):
        if not isinstance(val, str):
            raise ValueError('Target name must be an ascii string')

        if len(val.encode('ascii')) > 0xFF:
            raise ValueError('Target name must be smaller than 255 bytes')
            
        self._name = val
