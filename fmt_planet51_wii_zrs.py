# coding=utf-8

# DRAFT Planet 51 (Wii) plugin by Zhenёq
# https://github.com/Zheneq/Noesis-Plugins

from inc_noesis import *
import noesis
import rapi


def readMagic(bs, len = 4):
    try:
        return NoeBitStream(bs.readBytes(len)).readString()
    except UnicodeDecodeError:
        return ''


def round(bs):
    bs.seek((bs.tell() + 0x1f) & 0xFFFFFFE0)


def registerNoesisTypes():
    handle = noesis.register("Planet 51", ".zrs")
    noesis.setHandlerTypeCheck(handle, noepyCheckType)
    noesis.setHandlerLoadModel(handle, noepyLoadModel)
    return 1
    

def noepyCheckType(data):
    bs = NoeBitStream(data, NOE_BIGENDIAN)
    return bs.readUInt() == 0x6E0 and bs.readUInt() == 0x20000 and readMagic(bs) == "BASE"


def noepyLoadModel(data, mdlList):
    ctx = rapi.rpgCreateContext()
    ZRSFile(NoeBitStream(data), mdlList).load()
    rapi.rpgClearBufferBinds()
    return len(mdlList)
    

class ZRSFile:
    def __init__(self, bs, mdlList):
        self.bs = bs
        self.mdlList = mdlList
        bs.setEndian(NOE_BIGENDIAN)

        self.pos = []
        self.norm = []
        self.uvs = []
        
        
    def load(self):
        bs = self.bs

        bs.seek(0x60)

        header = {
            'modelCount': bs.readUInt(),
            'boneStuffCount': bs.readUInt(),  # = boneCount - 1
            'boneCount': bs.readUInt(),
            'unk3': bs.readUInt(),
            'unk4': bs.readUInt(),  # 0
            'unk5': bs.readUInt(),  # 0
            'unk6': bs.readUInt(),  # 0
            'unk7': bs.readUInt(),  # 0
        }

        print("header", header)


        print('-', "{:#x}".format(bs.tell()))

        for modelId in range(header['modelCount']):
            round(bs)

            modelHeader = {
                'unk0': bs.readUByte(),
                'unk1': bs.readUByte(),
                'lodCount': bs.readUByte(),
                'unk3': bs.readUByte(),
                'unk4': bs.readUByte(),
            }
            print("modelHeader", modelHeader)

            rapi.rpgSetMaterial("mat_" + str(modelId))


            for lodId in range(modelHeader['lodCount']):
                round(bs)

                unk = [bs.readUByte() for i in range(4)]

                meshCount = bs.readUInt()
                print("meshCount", meshCount)

                meshHeaders = [{
                    'unk' : [bs.readUInt() for j in range(20)],
                } for i in range(meshCount)]

                yy = [bs.readFloat() for i in range(6)]

                bufferFlags = bs.readUInt()
                bufferCount = bs.readUInt()
                bufferHeaders = [{
                    'flag': bs.readUInt(),
                    'addr': bs.readUInt(),
                    'num' : bs.readUInt(),
                    'size': bs.readUInt(),
                } for i in range(bufferCount)]

                dataBufferSize = bs.readUInt()
                dataBufferAddr = bs.tell()

                print("data buffer start @ {:#x}".format(bs.tell()))

                for bh in bufferHeaders:
                    print(bh)
                    ptr = dataBufferAddr + bh['addr']
                    bs.seek(ptr)
                    if   bh['flag'] == 0x1:
                        self.pos  = [[bs.readFloat() for j in range(3)] for i in range(bh['num'])]
                    elif bh['flag'] == 0x2:
                        self.norm = [[bs.readFloat() for j in range(3)] for i in range(bh['num'])]
                    elif bh['flag'] == 0x8:
                        self.uvs  = [[bs.readFloat() for j in range(2)] for i in range(bh['num'])]
                    elif bh['flag'] == 0x20:
                        self.vbon = [[bs.readUByte() for j in range(4)] for i in range(bh['num'])]
                    elif bh['flag'] == 0x40:
                        self.wei  = [[bs.readFloat() for j in range(4)] for i in range(bh['num'])]

                bs.seek(dataBufferAddr + bufferHeaders[-1]['addr'] + bufferHeaders[-1]['size'])

                print("data buffer end @ {:#x}".format(bs.tell()))

                rrCount = bs.readUInt()
                if not rrCount:
                    bs.seek(-4, NOESEEK_REL)
                    qqList = [{
                        'addr': bs.readUInt(),
                        'size': bs.readUInt(),
                    } for i in range(4)]
                    rrCount = bs.readUInt()

                meshes = []
                for i in range(meshCount):
                    rapi.rpgReset()
                    rapi.rpgSetOption(noesis.RPGOPT_BIGENDIAN, 1)
                    rapi.rpgSetUVScaleBias(NoeVec3((1,-1,0)), None)
                    self.readIndexBuffer()
                    rapi.rpgOptimize()
                    model = rapi.rpgConstructModel()
                    meshes.extend(model.meshes)

                self.mdlList.append(NoeModel(meshes))

                round(bs)

                print('-', "{:#x}".format(bs.tell()))
                ttCount = bs.readUInt()
                ttList = [{
                    'unk': bs.readUInt(),
                    'addr': bs.readUInt(),
                    'unk1': bs.readUInt(),
                } for i in range(ttCount)]
                print(ttList)

                print('-', "{:#x}".format(bs.tell()))

                bs.seek(1, NOESEEK_REL)

        bs.seek(-1, NOESEEK_REL)
        boneStuff = [bs.readUInt() for i in range(header['boneStuffCount'])]
        bones = [{
            'name': readMagic(bs, 0x40),
            'id': bs.readInt(),
            'parent': bs.readInt(),
            'unk0': bs.readInt(),
            'unk1': bs.readInt(),
            'unk2': bs.readInt(),
            'unk3': bs.readFloat(),
            'unk4': bs.readFloat(),
            'mat': NoeMat43([[bs.readFloat() for k in range(3)] for j in range(4)]),
            'scl': NoeVec3([bs.readFloat() for j in range(3)])
        } for i in range(header['boneCount'])]

        noeBones = [NoeBone(x['id'], x['name'], x['mat'], parentIndex=x['parent']) for x in bones]
        for m in self.mdlList:
            m.setBones(noeBones)

        
    def readIndexBuffer(self):
        bs = self.bs

        ptr = bs.tell()

        uuList = [bs.readUInt() for i in range(5)]

        # miLen = number of raised buffer flags
        if uuList[1] == 0xF:
            miLen = 4
        elif uuList[1] == 0x1F:
            miLen = 5

        round(bs)

        if bs.readUByte() != 0x90:
            print("Failed to read index buffer")
            bs.seek(ptr)
            return False
            
        count = bs.readUShort()
        
        print("{:#x} verts for {:#x} to {:#x}".format(count, bs.tell(), bs.tell() + count * miLen * 2))
        
        indices = [[bs.readUShort() for j in range(miLen)] for i in range(count)]

        rapi.immBegin(noesis.RPGEO_TRIANGLE)

        t = [-1 for i in range(miLen)]
        for x in indices:
            t = [max(t[i], x[i]) for i in range(miLen)]
            rapi.immUV2(self.uvs[x[3]])
            rapi.immNormal3(self.norm[x[1]])
            rapi.immBoneIndex(self.vbon[x[0]])
            rapi.immBoneWeight(self.wei[x[0]])
            rapi.immVertex3(self.pos[x[0]])
        print(t)
        rapi.immEnd()

        round(bs)

        return True
