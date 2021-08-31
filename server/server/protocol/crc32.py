
def crc32(data):
    crc=0xFFFFFFFF;
    for i in range(len(data)):
        for j in range(8):
            parity = (data[i]^crc)&1
            crc >>=1
            if parity:
                crc ^= 0xEDB88320
                crc >>=1

    return reverse32(crc)

def reverse32(n):
    return int('{:032b}'.format(n)[::-1], 2)