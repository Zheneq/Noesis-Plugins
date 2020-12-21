# coding=utf-8

# RSP[N] unpacker plugin by Zhenёq
# https://github.com/Zheneq/Noesis-Plugins

from inc_noesis import *
import noesis
import os


def readMagic(bs, len = 4):
    try:
        return bs.readBytes(len).decode("ascii").split('\0')[0]
    except UnicodeDecodeError:
        return ''


def registerNoesisTypes():
    handle = noesis.register("RSP archive", ".rsp")
    noesis.setHandlerExtractArc(handle, extract)
    return 1


def extract(fileName, fileLen, justChecking):
    if fileLen < 4:
        return False

    with open(fileName, "rb") as f:
        bs = NoeBitStream(f.read(), NOE_LITTLEENDIAN)

    magic = bs.readUInt()
    if magic != 0x00112233:
        return False

    if justChecking:
        return True

    names = extractNames(fileName)

    num = bs.readUInt()
    dataAddr = bs.readUInt()

    bs.seek(0x20)
    fileAddrs = []
    fileSizes = []
    for i in range(num):
        fileAddrs.append(bs.readUInt())  # zero-padded to a factor of 0x800
        fileSizes.append(bs.readUInt())

    for i in range(num):
        data = bs.getBuffer(fileAddrs[i], fileAddrs[i] + fileSizes[i])
        try:
            name = names[i]
        except IndexError:
            name = "file_{:08}".format(i)
        rapi.exportArchiveFile(name, data)

    return True


def extractNames(fileName):
    result = []

    tableFileName = fileName + "n"
    if not os.path.exists(tableFileName):
        print("RSPN not found")
        return result

    print("RSPN found")
    with open(fileName + "n", "rb") as f:
        bs = NoeBitStream(f.read(), NOE_LITTLEENDIAN)

    if readMagic(bs) != 'RSPN':
        print("RSPN magic does not match")
        return result

    num = bs.readUInt()
    print("RSPN: {} names".format(num))
    addrs = []
    for i in range(num):
        addr = bs.readUInt()
        index = bs.readUShort()
        zero = bs.readUByte()
        packageIndex = bs.readUByte()
        addrs.append(addr)

    for addr in addrs:
        bs.seek(addr)
        fileName = bs.readString()
        try:
            fileName = '.'.join(fileName.rsplit('_', 1))
        except:
            pass
        result.append(fileName)
        print(fileName)

    print("RSPN: {} names loaded".format(len(result)))

    return result
