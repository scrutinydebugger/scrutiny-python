from scrutiny.server.datalogging import definitions
from scrutiny.core.basic_types import *
from typing import List, Dict


def deinterleave_acquisition_data(data: bytes, config: definitions.Configuration, rpv_map: Dict[int, RuntimePublishedValue], encoding: definitions.Encoding) -> List[List[bytes]]:
    """
    Takes data writtent in the format [s1[n], s2[n], s3[n], s1[n+1], s2[n+1], s3[n+1], s1[n+2] ...]
    and put it in the format [s1[n], s1[n+1], s1[n+2]],  [s2[n], s2[n+1], s2[n+2]], [s3[n], s3[n+1], s3[n+2]]
    """
    data_out: List[List[bytes]] = []
    signals_def = config.get_signals()
    for i in range(len(signals_def)):
        data_out.append([])

    if encoding == definitions.Encoding.RAW:
        cursor = 0
        while cursor < len(data):
            for i in range(len(signals_def)):
                signaldef = signals_def[i]

                if isinstance(signaldef, definitions.MemoryLoggableSignal):
                    datasize = signaldef.size
                elif isinstance(signaldef, definitions.RPVLoggableSignal):
                    if signaldef.rpv_id not in rpv_map:
                        raise ValueError("RPV 0x%04X not part of given rpv_map" % signaldef.rpv_id)
                    rpv = rpv_map[signaldef.rpv_id]
                    datasize = rpv.datatype.get_size_byte()
                elif isinstance(signaldef, definitions.TimeLoggableSignal):
                    datasize = 4
                else:
                    raise NotImplementedError("Unsupported signal type")
                if len(data) < cursor + datasize:
                    raise ValueError('Not enough data in buffer for signal #%d' % i)
                data_out[i].append(data[cursor:cursor + datasize])
                cursor += datasize
    else:
        raise NotImplementedError('Unsupported encoding %s' % encoding)

    return data_out
