# coding=utf-8

# MT Framework 3DS texture plugin by Zhenёq
# https://github.com/Zheneq/Noesis-Plugins

# Acknowledgements:
# https://github.com/svanheulen/mhff/wiki/MH4U-rTexture-Format - header info

# Uses etc1tool.exe by onepiecefreak3
# https://github.com/onepiecefreak3/etc1tool/releases
# Put the executable into Noesis scenes folder


from inc_noesis import *
import noesis
import os
import subprocess


def readMagic(bs, length = 4):
    try:
        return NoeBitStream(bs.readBytes(length)).readString()
    except UnicodeDecodeError:
        return ''


def round(x, y):
    return (x + y - 1) // y * y


def registerNoesisTypes():
    handle = noesis.register("MT Framework 3DS Texture (partial support)", ".tex")
    noesis.setHandlerTypeCheck(handle, noepyCheckType)
    noesis.setHandlerLoadRGBA(handle, noepyLoadRGBA)
    return 1


def noepyCheckType(data):
    header = readHeader(NoeBitStream(data))
    return header['magic'] == 'TEX' and header['version'] == 0xA4


def noepyLoadRGBA(data, texList):
    bs = NoeBitStream(data)
    header = readHeader(bs)
    print(header)

    if header['textureCount'] != 1:
        return 0

    if header['format'] == 0x11:
        width = round(header['width'], 8)
        height = round(header['height'], 8)
        tex = bs.getBuffer(bs.tell(), bs.tell() + width * height * 3)
        tex = unswizzle(tex, width, height)
        texList.append(NoeTexture("default", width, height, tex, noesis.NOESISTEX_RGB24))

    elif header['format'] == 0xB or header['format'] == 0xC:
        width = round(header['width'], 4)
        height = round(header['height'], 4)

        alpha = 1 if header['format'] == 0xC else 0

        tex = bs.getBuffer(bs.tell(), bs.tell() + width * height * (alpha + 1) // 2)

        tempETC1filename = os.path.join(noesis.getScenesPath(), 'etc1')
        tempETC1file = open(tempETC1filename, 'wb')
        tempETC1file.write(tex)
        tempETC1file.close()

        try:
            subprocess.Popen([os.path.join(noesis.getScenesPath(), 'etc1tool.exe'), '-d', 'etc1', 'etc1-rgba', str(header['width']), str(header['height']), str(alpha)], cwd=noesis.getScenesPath()).wait()
        except WindowsError:
            noesis.messagePrompt("Please, download etc1tool.exe by onepiecefreak3 (https://github.com/onepiecefreak3/etc1tool/releases) and put the executable into Noesis scenes folder.")
            return 0
        os.remove(tempETC1filename)

        tempRGBAfilename = tempETC1filename + '-rgba'
        tempRGBAfile = open(tempRGBAfilename, 'rb')
        tex = tempRGBAfile.read()
        tempRGBAfile.close()
        os.remove(tempRGBAfilename)

        texList.append(NoeTexture("default", header['width'], header['height'], tex, noesis.NOESISTEX_RGBA32))
    else:
        print("Format not supported!")

    return len(texList)


def readHeader(bs):
    res = {}
    
    res['magic'] = readMagic(bs)

    t = bs.readUInt()
    res['version'] = t & 0xfff
    res['unk0'] = (t >> 12) & 0xfff
    res['sizeShift'] = (t >> 24) & 0xf
    res['cubeMap'] = (t >> 28) & 0xf
    
    t = bs.readUInt()
    res['mipCount'] = t & 0x3f
    res['width'] = (t >> 6) & 0x1fff
    res['height'] = (t >> 19) & 0x1fff

    res['textureCount'] = bs.readUByte()
    res['format'] = bs.readUByte()

    t = bs.readUShort()
    res['unk1'] = t & 0x1fff
    res['padding'] = (t >> 13) & 0x8

    return res


def unswizzle(buffer, width, height):
    bpp = 24
    l = 8
    m = 4
    s = 2
    stripSize = bpp * s // 8

    result = bytearray(width * height * bpp // 8)
    ptr = 0

    for y in range(0, height, l):
        for x in range(0, width, l):
            for y1 in range(0, l, m):
                for x1 in range(0, l, m):
                    for y2 in range(0, m, s):
                        for x2 in range(0, m, s):
                            for y3 in range(s):
                                idx = (((y + y1 + y2 + y3) * width) + x + x1 + x2) * bpp // 8
                                result[idx : idx+stripSize] = buffer[ptr : ptr+stripSize]
                                ptr += stripSize

    return result
