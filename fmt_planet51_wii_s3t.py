# coding=utf-8

# Planet 51 (Wii) texture plugin by Zhenёq
# https://github.com/Zheneq/Noesis-Plugins

from inc_noesis import *
import noesis
import rapi
import os
import lib_zq_nintendo_tex as nintex


def registerNoesisTypes():
    handle = noesis.register("Planet 51 (Wii) Texture", ".s3t")
    noesis.setHandlerTypeCheck(handle, noepyCheckType)
    noesis.setHandlerLoadRGBA(handle, noepyLoadRGBA)
    return 1


def noepyCheckType(data):
    bs = NoeBitStream(data, NOE_BIGENDIAN)
    header = readHeader(bs)
    return header['dataFormat'] in nintex.dataFormats and \
        nintex.getTextureSizeInBytes(header['width'], header['height'], header['dataFormat']) + 0x20 <= bs.getSize()
    # and always 4 mipmaps?


def noepyLoadRGBA(data, texList):
    bs = NoeBitStream(data, NOE_BIGENDIAN)
    header = readHeader(bs)
    tex = nintex.readTexture(bs, header['width'], header['height'], header['dataFormat'])
    texList.append(tex)
    return len(texList)


def readHeader(bs):
    return {
        'dataFormat' : bs.readUInt(),
        'width'      : bs.readUInt(),
        'height'     : bs.readUInt(),
        'unk0'       : bs.readUInt(),
        'unks'       : [bs.readUByte() for i in range(16)],
    }
