# coding=utf-8

# Fire Emblem .gs/.g plugin by Zhenёq
# https://github.com/Zheneq/Noesis-Plugins

from inc_noesis import *
import noesis
import rapi

UV_SCALE = 0x4000
NORM_SCALE = 0x800
VERT_SCALE = 0x800

debug = 0

def readMagic(bs, len = 4):
    try:
        return NoeBitStream(bs.readBytes(len)).readString()
    except UnicodeDecodeError:
        return ''

def registerNoesisTypes():
    handle = noesis.register("Fire Emblem Model", ".gs")
    noesis.setHandlerTypeCheck(handle, lambda data: GSFile(NoeBitStream(data), []).check())
    noesis.setHandlerLoadModel(handle, noepyLoadModel)
    handle = noesis.register("Fire Emblem Skeleton", ".g")
    noesis.setHandlerTypeCheck(handle, lambda data: GFile(NoeBitStream(data), []).check())
    noesis.setHandlerLoadModel(handle, lambda data, mdlList: GFile(NoeBitStream(data), mdlList).load())
    return 1

def noepyLoadModel(data, mdlList):
    ctx = rapi.rpgCreateContext()
    rapi.rpgSetOption(noesis.RPGOPT_TRIWINDBACKWARD, 1)
    GSFile(NoeBitStream(data), mdlList).load()
    rapi.rpgClearBufferBinds()
    return len(mdlList)

class GFile:
    def __init__(self, bs, mdlList):
        self.bs = bs
        self.mdlList = mdlList
        bs.setEndian(NOE_BIGENDIAN)

    def check(self):
        return self.bs.readUInt() == 0

    def load(self):
        bs = self.bs

        junk = bs.readUInt()
        namesAddr = bs.readUInt()
        boneNum = bs.readUInt()
        dataAddr = bs.readUInt()

        bones = [{
            '_id': i,
            'parent': bs.readInt(),
            'unk0': [bs.readInt() for i in range(3)],
            'mat': NoeMat44([[bs.readFloat() for j in range(4)] for i in range(4)]),
            'unk1': [bs.readFloat() for i in range(2)],
            'pos': NoeVec3([bs.readFloat() for i in range(3)]),
            'unk2': [bs.readFloat() for i in range(22)],
            'mat1': [[bs.readFloat() for j in range(4)] for i in range(3)],
            'unk3': bs.readUShort(),  # 0x10 * i
            'unk4': bs.readUShort(),  # 0x1
            'nameAddr': bs.readUInt()
        } for i in range(boneNum)]  # F4 bytes


        for x in bones:
            bs.seek(namesAddr + x['nameAddr'])
            x['_name'] = bs.readString()

            x['_mat1'] = []
            x['_mat1'].extend(x['mat1'])
            x['_mat1'].append([1,1,1,0])
            x['_mat1'] = NoeMat44(x['_mat1'])

        for x in bones:
            x['_parentName'] = bones[x['parent']]['_name'] if x['parent'] >= 0 else 'NONE'

        noeBones = [NoeBone(x['_id'], x['_name'] + '_' + str(x['_id']), -x['mat'].transpose().toMat43(), parentIndex=x['parent']) for x in bones]
        self.mdlList.append(NoeModel(bones=noeBones))

        if debug:
            for x in bones:
                for y in x:
                    print(y, ':', x[y])
                print()
            print()

        return len(self.mdlList)


class GSFile:
    def __init__(self, bs, mdlList):
        self.bs = bs
        self.mdlList = mdlList
        bs.setEndian(NOE_BIGENDIAN)

        self.pos = []
        self.norm = []
        self.uvs = []
        self.bones = []

    def check(self):
        return self.bs.readUInt() == self.bs.getSize()

    def loadSkeleton(self):
        skelFile = os.path.join(rapi.getDirForFilePath(rapi.getInputName()), 'skeleton.g')
        skelMdlList = []
        try:
            with open(skelFile, 'rb') as skel:
                GFile(NoeBitStream(skel.read()), skelMdlList).load()
        except IOError:
            return False

        self.bones = skelMdlList[0].bones
        return True

    def load(self):
        bs = self.bs

        fileSize = bs.readUInt()
        tableAddr = bs.readUInt()
        num = bs.readUInt()

        bs = NoeBitStream(bs.getBuffer(0x20, bs.getSize()), NOE_BIGENDIAN)

        rootNameAddr = bs.readUInt()
        unk0 = [bs.readFloat() for i in range(8)]

        if debug:
            print("unk0", unk0)

        addrs = [bs.readUInt() for i in range(10)]
        nums  = [bs.readUShort() for i in range(10)]

        if debug:
            print("addrs", addrs)
            print("nums", nums)

        # uv buffer
        if addrs[2]:
            bs.seek(addrs[2])
            self.uvs = [[bs.readShort() / UV_SCALE for j in range(2)] for i in range(nums[2])]

        # materials
        if addrs[4]:
            bs.seek(addrs[4])
            part4 = [{
                'nameAddr': bs.readUInt(),
                'unk': [bs.readUInt() for j in range(4)],
                'addr': bs.readUInt(),
                'junk': [bs.readUInt() for j in range(2)],
            } for i in range(nums[4])]

            for x in part4:
                bs.seek(x['nameAddr'])
                x['_name'] = bs.readString()

            if debug:
                print(4)
                for x in part4:
                    print('\t', x)
                print()
                print()

        # ?
        if addrs[5]:
            bs.seek(addrs[5])
            part5 = [{
                'nameAddr': bs.readUInt(),
                'unk': [bs.readFloat() for j in range(6)],
                'id': bs.readUShort(),
                'junk': [bs.readUShort() for j in range(3)],
            } for i in range(nums[5])]

            for x in part5:
                bs.seek(x['nameAddr'])
                x['_name'] = bs.readString()


            if debug:
                print(5)
                for x in part5:
                    print('\t', x)
                print()
                print()

        # ?
        if addrs[7]:
            bs.seek(addrs[7])
            # points to one of part6's that is not referenced by another part6

            if not addrs[6]:
                addrs[6] = addrs[7]

        # buffers
        if addrs[9]:
            bs.seek(addrs[9])

            part9 = {
                'addr0': bs.readUInt(),
                'addr1': bs.readUInt(),
                'num0': bs.readUShort(),
                'numVerts': bs.readUShort(),
                'unk0': bs.readUShort(),
                'unk1': bs.readUShort(),
            }

            if debug:
                print(9)
                print('\t', part9)
                print()

            bs.seek(addrs[9] + part9['addr0'])
            part9['data0'] = [[bs.readShort() for j in range(12)] for i in range(part9['num0'])]

            if debug:
                for x in part9['data0'][0:32]:
                    print('\t', x)
                print()

            bs.seek(addrs[9] + part9['addr1'])

            for i in range(part9['numVerts']):
                self.pos.append([bs.readShort() / VERT_SCALE for j in range(3)])
                self.norm.append([bs.readShort() / NORM_SCALE for j in range(3)])

            if debug:
                print('pos')
                for x in self.pos[-32:-1]:
                    print('\t', x)
                print('norm')
                for x in self.norm[-32:-1]:
                    print('\t', x)
                print()

        # tris
        if addrs[6]:
            bs.seek(addrs[6])
            part6 = [{
                'part5Addr': bs.readUInt(),
                'nextAddr': bs.readUInt(),
                'unk0': [bs.readUByte() for j in range(4)],
                'id': bs.readUShort(),
                'unk2': [bs.readUByte() for j in range(6)],
                'triAddr': bs.readUInt(),
                'triSize': bs.readUInt(),
                'junk': bs.readUInt(),
            } for i in range(nums[6])]


            if debug:
                print(6)
                for x in part6:
                    print('\t', x)
                print()
                print()

            for x in part6:
                if addrs[4]:
                    rapi.rpgSetMaterial(part4[x['unk0'][3]]['_name'])

                # building tristrips
                bs.seek(x['triAddr'])

                while bs.tell() < x['triAddr'] + x['triSize']:
                    mag = bs.readUByte()
                    if mag != 0x98:
                        break

                    rapi.immBegin(noesis.RPGEO_TRIANGLE_STRIP)

                    num = bs.readUShort()
                    for i in range(num):
                        vert = bs.readUShort()
                        norm = bs.readUShort()
                        uv   = bs.readUShort()

                        rapi.immNormal3(self.norm[norm])
                        rapi.immUV2(self.uvs[uv])
                        rapi.immVertex3(self.pos[vert])

                    rapi.immEnd()

            rapi.rpgOptimize()

            mdl = rapi.rpgConstructModel()

            self.loadSkeleton()
            mdl.setBones(self.bones)

            self.mdlList.append(mdl)

        ####################################
        # bs.seek(tableAddr)
        # table = [bs.readUInt() for i in range(num)]
