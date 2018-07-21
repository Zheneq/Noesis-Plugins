# coding=utf-8

# Fire Emblem .pac unpacker plugin by Zhenёq
# https://github.com/Zheneq/Noesis-Plugins

from inc_noesis import *
import noesis
import rapi
import os
from functools import reduce

debug = 1

def readMagic(bs, len = 4):
    try:
        return bs.readBytes(len).decode("ascii").split('\0')[0]
    except UnicodeDecodeError:
        return ''


def readString(bs):
    buf = bytearray()
    while 1:
        buf.append(bs.readUByte())
        if not buf[-1]: break
    try:
        return buf.decode("ascii").split('\0')[0]
    except UnicodeDecodeError:
        return ''


def registerNoesisTypes():
    handle = noesis.register("Fire Emblem archive", ".pak")
    noesis.setHandlerExtractArc(handle, extract)
    return 1


def extract(fileName, fileLen, justChecking):
    if fileLen < 4:
        return False

    with open(fileName, "rb") as f:
        bs = NoeBitStream(f.read(), NOE_BIGENDIAN)

    if readMagic(bs) != 'pack':
        return False

    numFiles = bs.readUShort()
    junk = bs.readUShort()

    fileInfo = [{
        'junk': bs.readUInt(),
        'name': bs.readUInt(),
        'data': bs.readUInt(),
        'size': bs.readUInt(),
    } for i in range(numFiles)]

    valid = reduce(lambda a, b: a and b, [x['data'] + x['size'] <= fileLen for x in fileInfo])

    if not valid or justChecking:
        return valid

    for x in fileInfo:
        bs.seek(x['name'])
        name = readString(bs)
        data = bs.getBuffer(x['data'], x['data'] + x['size'])
        rapi.exportArchiveFile(name, data)

    return True
