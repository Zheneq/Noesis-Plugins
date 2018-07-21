# coding=utf-8

# TPL Wii texture plugin by Zhenёq
# https://github.com/Zheneq/Noesis-Plugins

# Based on specs from http://wiki.tockdom.com/wiki/TPL_(File_Format)

from inc_noesis import *
import noesis
import lib_zq_nintendo_tex as nintex


debug = 0


def registerNoesisTypes():
    handle = noesis.register("Wii Texture Library", ".tpl")
    noesis.setHandlerTypeCheck(handle, noepyCheckType)
    noesis.setHandlerLoadRGBA(handle, noepyLoadRGBA)
    return 1


def noepyCheckType(data):
    bs = NoeBitStream(data, NOE_BIGENDIAN)
    return bs.getSize() >= 4 and bs.readUInt() == 0x0020AF30


def noepyLoadRGBA(data, texList):
    bs = NoeBitStream(data, NOE_BIGENDIAN)

    magic = bs.readUInt()
    count = bs.readUInt()
    imageTblAddr = bs.readUInt()

    bs.seek(imageTblAddr)
    data = [{
        'imageDataAddr':  bs.readUInt(),
        'imagePaletteAddr': bs.readUInt()
    } for i in range(count)]

    for x in data:
        paletteBuffer = None
        paletteFormat = None

        if x['imagePaletteAddr']:
            bs.seek(x['imagePaletteAddr'])
            palette = {
                'num':      bs.readUShort(),
                'unpacked': bs.readUByte(),
                'junk':     bs.readUByte(),
                'format':   bs.readUInt(),
                'addr':     bs.readUInt()
            }
            paletteBuffer = bs.getBuffer(palette['addr'], palette['addr'] + nintex.getPaletteSizeInBytes(palette['format'], palette['num']))
            paletteFormat = palette['format']

        bs.seek(x['imageDataAddr'])
        image = {
            'height':        bs.readUShort(),
            'width':         bs.readUShort(),
            'format':        bs.readUInt(),
            'addr':          bs.readUInt(),
            'wrapS':         bs.readUInt(),
            'wrapT':         bs.readUInt(),
            'minFilter':     bs.readUInt(),
            'magFilter':     bs.readUInt(),
            'lodBias':       bs.readFloat(),
            'edgeLodEnable': bs.readUByte(),
            'minLod':        bs.readUByte(),
            'maxLod':        bs.readUByte(),
            'unpacked':      bs.readUByte(),
        }

        if debug:
            print('image: {:#x}'.format(x['imageDataAddr']))
            print(image)
            print('palette: {:#x}'.format(x['imagePaletteAddr']))
            if x['imagePaletteAddr']:
                print(palette)

        bs.seek(image['addr'])
        tex = nintex.readTexture(bs, image['width'], image['height'], image['format'], paletteBuffer, paletteFormat)
        texList.append(tex)

    return len(texList)
