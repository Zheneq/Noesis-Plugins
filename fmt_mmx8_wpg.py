# MegamanX8 wpg plugin by Zheneq
# https://github.com/Zheneq/Noesis-Plugins

from inc_noesis import *

import noesis

#rapi methods should only be used during handler callbacks
import rapi

#registerNoesisTypes is called by Noesis to allow the script to register formats.
#Do not implement this function in script files unless you want them to be dedicated format modules!
def registerNoesisTypes():
    handle = noesis.register("MegamanX8 Texture Archive", ".wpg")
    noesis.setHandlerTypeCheck(handle, noepyCheckType)
    noesis.setHandlerLoadRGBA(handle, noepyLoadRGBA)
    # noesis.setHandlerWriteRGBA(handle, noepyWriteRGBA)

    # noesis.addOption(handle, "-shift", "<arg> is texture shift from the beginning of data block", noesis.OPTFLAG_WANTARG)
    # noesis.addOption(handle, "-size", "<arg> is size of texture in bytes", noesis.OPTFLAG_WANTARG)
    return 1

#check if it's this type based on the data
def noepyCheckType(data):
    return WPGFile([], data = data).check

def noepyLoadRGBA(data, texList):
    return WPGFile(texList, data = data).load()

class WPGFile:
    HEADERSIZE = 32
    TGAHEADERSIZE = 18

    def __init__(self, texList, name = None, map = None, path = None, data = None):

        self.name = name
        if not self.name: self.name = rapi.getInputName().split('\\')[-1].split('/')[-1]
        self.map = map
        self.texList = texList

        if data:
            self.bs = NoeBitStream(data)
        elif path:
            texFile = open(path, 'rb').read()
            self.bs = NoeBitStream(texFile)
        else:
            print("WPG: No input provided!")

        self.bs.seek(0)
        header = self.bs.readBytes(self.HEADERSIZE).decode('ascii').split('\0')[0]
        self.check = header == "wpg"

    def load(self):
        self.count = 0
        if not self.check:
            return 0

        if self.map:
            for x in self.map:
                self.load_sub(self.HEADERSIZE + x['shift'], x['size'])
        else:
            cursor = self.HEADERSIZE
            while cursor < self.bs.dataSize:
                tex = self.load_sub(cursor, self.bs.dataSize - cursor)

                if not tex:
                    break

                if tex.pixelType == noesis.NOESISTEX_RGBA32:
                    BPP = 4
                elif tex.pixelType == noesis.NOESISTEX_RGB24:
                    BPP = 3
                else:
                    BPP = 4
                    print("Unsupported pixel type")
                cursor += tex.width * tex.height * BPP + self.TGAHEADERSIZE

        print("Loaded", self.count, "textures")
        return self.count

    def load_sub(self, start, size):
        self.bs.seek(start)
        buffer = self.bs.readBytes(size)
        tex = rapi.loadTexByHandler(buffer, '.tga')
        if not tex:
            return 0
        tex.name = "{0}.{1:02}.tga".format(self.name, self.count)
        self.count += 1
        self.texList.append(tex)
        return tex