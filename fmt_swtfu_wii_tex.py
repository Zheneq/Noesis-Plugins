# coding=utf-8

# Star Wars: The Force Unleashed texture plugin by Zhenёq
# https://github.com/Zheneq/Noesis-Plugins

from inc_noesis import *
import noesis
import rapi
import os
import lib_zq_nintendo_tex as nintex


def registerNoesisTypes():
    handle = noesis.register("Star Wars: The Force Unleashed (Wii) Texture", ".tex")
    noesis.setHandlerTypeCheck(handle, noepyCheckType)
    noesis.setHandlerLoadRGBA(handle, noepyLoadRGBA)
    return 1


def noepyCheckType(data):
    bs = NoeBitStream(data, NOE_BIGENDIAN)
    header = readHeader(bs)
    return header['version'] in versions and header['size'] + 0x20 <= bs.getSize()


versions = {
    0x00: nintex.NINTEX_RGBA32,
    0x4b: nintex.NINTEX_IA8,
    0x4c: nintex.NINTEX_CMPR,
}

def noepyLoadRGBA(data, texList):
    bs = NoeBitStream(data, NOE_BIGENDIAN)
    header = readHeader(bs)
    tex = nintex.readTexture(bs, header['width'], header['height'], versions[header['version']])
    tex.name = rapi.getInputName()
    texList.append(tex)
    return len(texList)


def readHeader(bs):
    return {
        'version' : bs.readUInt(),
        'width'   : bs.readUInt(),
        'height'  : bs.readUInt(),
        'size'    : bs.readUInt(),
        'unk0'    : bs.readUInt(),
        'mipmaps' : bs.readUInt(),
        'unk1'    : bs.readUInt(),
        'unk2'    : bs.readUInt(),
    }