# coding=utf-8

# Silent Hill: Shattered Memories texture plugin by Zhenёq
# https://github.com/Zheneq/Noesis-Plugins

from inc_noesis import *
import noesis
import rapi
import os
import lib_zq_nintendo_tex as nintex


def readMagic(bs, len = 4):
    try:
        return NoeBitStream(bs.readBytes(len)).readString()
    except UnicodeDecodeError:
        return ''


def registerNoesisTypes():
    handle = noesis.register("Silent Hill: Shattered Memories (Wii) Texture", ".tx")
    noesis.setHandlerTypeCheck(handle, noepyCheckType)
    noesis.setHandlerLoadRGBA(handle, noepyLoadRGBA)
    return 1


def noepyCheckType(data):
    bs = NoeBitStream(data, NOE_BIGENDIAN)
    header = readHeader(bs)
    return header['dataFormat'] in nintex.dataFormats and header['size'] + 0x90 <= bs.getSize()


def noepyLoadRGBA(data, texList):
    bs = NoeBitStream(data, NOE_BIGENDIAN)
    header = readHeader(bs)
    tex = nintex.readTexture(bs, header['width'], header['height'], header['dataFormat'])
    tex.name = header['name']
    texList.append(tex)
    return len(texList)


def readHeader(bs):
    return {
        'unks': [bs.readUInt() for i in range(15)],
        'name': readMagic(bs, 0x40),
        'unk0': bs.readUInt(),
        'width': bs.readUShort(),
        'height': bs.readUShort(),
        'unk1': bs.readUByte(),
        'mips': bs.readUByte(),
        'dataFormat': bs.readUByte(),
        'unk2': bs.readUByte(),
        'unk3': bs.readUInt(),
        'size': bs.readUInt(),
    }
