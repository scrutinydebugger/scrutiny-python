
def crc32(data):
    crc=0xFFFFFFFF;
    for i in range(len(data)):
        byte = data[i]
        for j in range(8):
            lsb = (byte^crc)&1
            crc >>=1
            if lsb:
                crc ^= 0xEDB88320
            byte >>= 1

    return not32(crc)

def not32(n):
    return (~n) & 0xFFFFFFFF