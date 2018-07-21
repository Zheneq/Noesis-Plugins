# coding=utf-8

# Fire Emblem .gs/.g plugin by Zhenёq
# https://github.com/Zheneq/Noesis-Plugins

from inc_noesis import *
import noesis
import rapi
import math
import glob

# load vertex colors
vertex_colors = 0
# load textures
textures = 1

debug = 0
skel_debug = 0

# use tpl if present
tpl = False
try:
    import fmt_wii_tpl
    tpl = True
except ImportError:
    pass

# constant for composite buffer
NORM_SCALE = 0x800
VERT_SCALE = 0x800
WEI_SCALE  = 0x100


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
            'matBoneToWorld': [[bs.readFloat() for j in range(4)] for i in range(3)],
            'tr': {
                'scl': NoeVec3([bs.readFloat() for i in range(3)]),  # ???
                'rot': NoeVec3([bs.readFloat() for i in range(3)]),  # ???
                'pos': NoeVec3([bs.readFloat() for i in range(3)])
            },  # same as mat?
            'unk1': [bs.readFloat() for i in range(3)],
            'pos':  [bs.readFloat() for i in range(3)],  # == unk3 usually.
            'unk3': [bs.readFloat() for i in range(3)],
            'unk4': [bs.readFloat() for i in range(13)],
            'mat': [[bs.readFloat() for j in range(4)] for i in range(3)],
            'unk5': bs.readUShort(),  # 0x10 * i
            'unk6': bs.readUShort(),  # 0x1
            'nameAddr': bs.readUInt()
        } for i in range(boneNum)]  # F4 bytes

        usedNames = set()
        for x in bones:
            bs.seek(namesAddr + x['nameAddr'])
            x['_name'] = bs.readString()

            noeName = x['_name'].lower()

            if noeName in usedNames:
                x['_name'] += '_' + str(x['_id'])
            else:
                usedNames.add(noeName)

            x['_matBoneToWorld'] = []
            x['_matBoneToWorld'].extend(x['matBoneToWorld'])
            x['_matBoneToWorld'].append([0,0,0,1])
            x['_matBoneToWorld'] = NoeMat44(x['_matBoneToWorld']).transpose()

            x['_mat'] = []
            x['_mat'].extend(x['mat'])
            x['_mat'].append([0,0,0,1])
            x['_mat'] = NoeMat44(x['_mat']).transpose()

            x['_bone'] = NoeMat43().translate(x['pos']) * x['_matBoneToWorld'].toMat43().inverse()

        for x in bones:
            x['_parentName'] = bones[x['parent']]['_name'] if x['parent'] >= 0 else 'NONE'

        # noeBones = [NoeBone(x['_id'], x['_name'], x['_mat'].toMat43(), parentIndex=x['parent']) for x in bones]
        # noeBones = rapi.multiplyBones(noeBones)
        # for x in noeBones:
        #     x.setMatrix(NoeMat43().translate(bones[x.index]['pos']) * x.getMatrix())
        noeBones = [NoeBone(x['_id'], x['_name'], x['_bone'], parentIndex=x['parent']) for x in bones]

        self.mdlList.append(NoeModel(bones=noeBones))

        if skel_debug:
            for x in bones:
                for y in x:
                    print(y, ':', x[y])
                print()
            print()

            for x in noeBones:
                print('\t', x.getMatrix() == bones[x.index]['_bone'])
                print('\t', x.getMatrix())
                print('\t', bones[x.index]['_bone'])
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
        self.colors = []
        self.materials = []
        self.meshes = []
        self.chunks = []
        self.compBuffer = []
        self.compPos = []
        self.compNorm = []
        self.boneIdx = []
        self.boneWei = []

        self.bones = []
        self.texList = []
        self.noeMaterials = NoeModelMaterials([], [])

    def check(self):
        return self.bs.readUInt() == self.bs.getSize()

    def loadSkeleton(self):
        skelFiles = [os.path.join(rapi.getDirForFilePath(rapi.getInputName()), 'skeleton.g'), rapi.getExtensionlessName(rapi.getInputName()) + '.g']

        if debug:
            print('Looking for skeleton in:', skelFiles)

        skelMdlList = []

        for skelFile in skelFiles:
            try:
                with open(skelFile, 'rb') as skel:
                    GFile(NoeBitStream(skel.read()), skelMdlList).load()
                break
            except IOError:
                continue
        else:
            return False

        self.bones = skelMdlList[0].bones
        return True

    def loadTextures(self):
        if tpl and textures:
            name = rapi.getExtensionlessName(rapi.getInputName())
            tplFiles = [name + '.tpl']

            localFiles = glob.glob(os.path.join(rapi.getDirForFilePath(rapi.getInputName()), '*.tpl'))
            if localFiles:
                tplFiles.extend(localFiles)

            localFiles = glob.glob(os.path.join(rapi.getDirForFilePath(rapi.getInputName()), os.path.pardir, '*.tpl'))
            if localFiles:
                tplFiles.extend(localFiles)

            if debug:
                print('Looking for textures in:', tplFiles)

            for tplFile in tplFiles:
                try:
                    with open(tplFile, 'rb') as texFile:
                        data = texFile.read()
                        if fmt_wii_tpl.noepyCheckType(data):
                            fmt_wii_tpl.noepyLoadRGBA(data, self.texList)
                            name = tplFile
                            break
                except IOError:
                    continue
            else:
                return False

            for i in range(len(self.texList)):
                self.texList[i].name = rapi.getExtensionlessName(rapi.getLocalFileName(name)) + '_' + str(i)
            return True

        return False

    def load(self):
        bs = self.bs

        fileSize = bs.readUInt()
        tableAddr = bs.readUInt()
        tableNum = bs.readUInt()

        bs = NoeBitStream(bs.getBuffer(0x20, bs.getSize()), NOE_BIGENDIAN)

        rootNameAddr = bs.readUInt()
        unk0 = [bs.readFloat() for i in range(8)]

        if debug:
            print("unk0", unk0)

        addrs = [bs.readUInt() for i in range(10)]
        nums  = [bs.readUShort() for i in range(8)]

        vertScale = 1 << bs.readUByte()
        normScale = 1 << bs.readUByte()
        uvScale   = 1 << bs.readUByte()

        if debug:
            print("addrs", ['{:#x}'.format(x) for x in addrs])
            print("nums", ['{:#x}'.format(x) for x in nums])
            print("addrs", addrs)
            print("nums", nums)
            print("vertScale", vertScale, "normScale", normScale, "uvScale", uvScale)

        if nums[7] != 0:
            print('WARNING! nums[7] != 0')

        unparsedTris = set()

        self.loadSkeleton()

        # vertex buffer
        if addrs[0]:
            bs.seek(addrs[0])
            self.pos = [[bs.readShort() / vertScale for j in range(3)] for i in range(nums[0])]

        # normal buffer
        if addrs[1]:
            bs.seek(addrs[1])
            self.norm = [[bs.readByte() / normScale for j in range(3)] for i in range(nums[1])]

        # uv buffer
        if addrs[2]:
            bs.seek(addrs[2])
            self.uvs = [[bs.readShort() / uvScale for j in range(2)] for i in range(nums[2])]

        # vertex color buffer
        if addrs[3]:
            bs.seek(addrs[3])
            self.colors = [[bs.readUByte() for j in range(4)] for i in range(nums[3])]

        # materials
        if addrs[4]:
            bs.seek(addrs[4])
            self.materials = [{
                'nameAddr': bs.readUInt(),
                'unk0':    [bs.readUByte() for j in range(2)],
                'texNum':   bs.readUByte(),
                'unk1':     bs.readUByte(),
                'color0':  [bs.readUByte() for j in range(4)],
                'color1':  [bs.readUByte() for j in range(4)],
                'color2':  [bs.readUByte() for j in range(4)],
                'texAddr':  bs.readUInt(),
                'junk':    [bs.readUInt() for j in range(2)],
            } for i in range(nums[4])]

            maxTexId = -1
            for x in self.materials:
                bs.seek(x['nameAddr'])
                x['_name'] = bs.readString()

                bs.seek(x['texAddr'])
                x['_tex'] = [{
                    'unk0': [bs.readUShort() for j in range(2)],
                    'id':    bs.readUShort(),
                    'unk1': [bs.readUShort() for j in range(5)],
                    'unk2':  bs.readFloat(),
                    'unk3':  bs.readFloat(),
                    'unk4':  bs.readUInt(),
                } for i in range(x['texNum'])]

                for y in x['_tex']:
                    if y['id'] > maxTexId:
                        maxTexId = y['id']

            if debug:
                print('4 - materials')
                for x in self.materials:
                    print('\t', x)
                print()
                print()

            self.loadTextures()
            if len(self.texList) > maxTexId:
                self.noeMaterials = NoeModelMaterials(self.texList, [NoeMaterial(x['_name'], self.texList[x['_tex'][0]['id']].name if x['_tex'] else 'no_texture') for x in self.materials])

        # meshes
        if addrs[5]:
            if not addrs[5] & 0x80000000:  # else: maybe a standard shape, maybe a glitch (PoR/zmap/bmap28/map.cmp/fire_01.gs)
                bs.seek(addrs[5])
                self.meshes = [{
                    'nameAddr': bs.readUInt(),
                    'unk0':    [bs.readFloat() for j in range(3)],  # bounds ?
                    'unk1':    [bs.readFloat() for j in range(3)],  #
                    'bone':     bs.readUShort(),
                    'junk':    [bs.readUShort() for j in range(3)],
                } for i in range(nums[5])]

                for x in self.meshes:
                    bs.seek(x['nameAddr'])
                    x['_name'] = bs.readString()

                if debug:
                    print('5 - meshes')
                    for x in self.meshes:
                        print('\t', x)
                    print()
                    print()

        # ?
        if addrs[7]:
            if not addrs[6]:
                addrs[6] = addrs[7]
            else:
                unparsedTris.add(addrs[7])

        # ?
        if addrs[8]:
            if not addrs[6]:
                addrs[6] = addrs[8]
            else:
                unparsedTris.add(addrs[8])

        # composite buffer (vertices + normals + weights)
        if addrs[9]:
            bs.seek(addrs[9])

            self.compBuffer = {
                'addrWeights': bs.readUInt(),
                'addrVerts': bs.readUInt(),
                'numWeights': bs.readUShort(),
                'numVerts': bs.readUShort(),
                'unk0': bs.readUShort(),
                'unk1': bs.readUShort(),
            }

            if debug:
                print('9 - composite buffer')
                print('\t', self.compBuffer)
                print()

            # weights
            bs.seek(addrs[9] + self.compBuffer['addrWeights'])
            self.compBuffer['dataWeights'] = [{
                'indices':   [bs.readShort() for j in range(4)],
                'weights':   [bs.readUByte() / WEI_SCALE for j in range(4)],
                'start':      bs.readUInt(),
                'size':       bs.readUShort(),
                'startAdd':   bs.readUByte(),
                'numIndices': bs.readUByte(),
                'vertCount':  bs.readUShort(),
                'unk1':       bs.readUShort(),
            } for i in range(self.compBuffer['numWeights'])]

            self.boneIdx = [[0]] * self.compBuffer['numVerts']
            self.boneWei = [[1.0]] * self.compBuffer['numVerts']

            for x in self.compBuffer['dataWeights']:
                x['_indices'] = list(filter((-1).__ne__, x['indices']))
                if len(x['_indices']) > 1:
                    x['_weights'] = x['weights'][:len(x['_indices'])]
                else:
                    x['_weights'] = [1.0]

                startVert = (x['start'] + x['startAdd']) // 0xC
                for i in range(startVert, startVert + x['vertCount']):
                    self.boneIdx[i] = x['_indices']
                    self.boneWei[i] = x['_weights']

            # pos / norm
            bs.seek(addrs[9] + self.compBuffer['addrVerts'])

            for i in range(self.compBuffer['numVerts']):
                self.compPos.append([bs.readShort() / VERT_SCALE for j in range(3)])
                self.compNorm.append([bs.readShort() / NORM_SCALE for j in range(3)])

        # tris
        if addrs[6]:

            bs.seek(addrs[6])
            self.chunks = [{
                'meshAddr':       bs.readUInt(),
                'nextAddr':       bs.readUInt(),
                'format':         bs.readUShort(),
                'matId':          bs.readUShort(),
                'bone':           bs.readUShort(),
                'unk1':          [bs.readUByte() for j in range(4)],
                'format2':        bs.readUByte(),
                'unk2':           bs.readUByte(),
                'triAddr':        bs.readUInt(),
                'triSize':        bs.readUInt(),
                'boneSubsetAddr': bs.readUInt(),
            } for i in range(nums[6])]

            # just checking it to be sure we aren't missing anything
            for i in range(nums[6]):
                unparsedTris.discard(addrs[6] + i * 32)
            if unparsedTris:
                print('WARNING! Buffers left unparsed:', unparsedTris)

            for x in self.chunks:
                x['_meshId'] = (x['meshAddr'] - addrs[5]) // 0x24

                if x['boneSubsetAddr']:
                    bs.seek(x['boneSubsetAddr'])
                    mark = bs.readUByte()
                    if mark != 0x10:
                        print("WARNING! Unexpected mark.")

                    count = bs.readUByte()
                    x['_boneSubset'] = [bs.readUByte() for i in range(count)]

            for x in self.chunks:
                rapi.rpgSetName(self.meshes[x['_meshId']]['_name'] + '_' + str(x['_meshId']))  # name alone is often just "none"

                if self.materials:
                    rapi.rpgSetMaterial(self.materials[x['matId']]['_name'])

                bUseCompBuffer       = not not x['format'] & 1  # complex vertex weights
                bSingleBonePerVertex = not not x['format'] & 2  # simple vertex weights
                bHasColor            = not not x['format2'] & 0x10
                bHasUV2              = not not x['format2'] & 0x80
                # x['format2'] & 0x0F == 6
                # x['format2'] & 0x20 == 0
                # x['format2'] & 0x40 == 1

                if debug:
                    print('\tBuilding chunk:', x)
                    print('\t\t bUseCompBuffer\t\t',     bUseCompBuffer)
                    print('\t\t bSingleBonePerVertex\t', bSingleBonePerVertex)
                    print('\t\t bHasColor\t\t',          bHasColor)
                    print('\t\t bHasUV2\t\t\t',          bHasUV2)

                # building tristrips
                bs.seek(x['triAddr'])

                while bs.tell() < x['triAddr'] + x['triSize']:
                    mag = bs.readUByte()
                    if mag != 0x98:
                        break

                    rapi.immBegin(noesis.RPGEO_TRIANGLE_STRIP)

                    num = bs.readUShort()

                    try:
                        for i in range(num):
                            rapi.immBoneIndex([x['bone']])
                            rapi.immBoneWeight([1.0])

                            if bSingleBonePerVertex:
                                bone = bs.readUByte()
                                rapi.immBoneIndex([x['_boneSubset'][bone // 3]])

                            vert = bs.readUShort()
                            norm = bs.readUShort()

                            if bHasColor:
                                col = bs.readUShort()
                                if vertex_colors:
                                    rapi.immColor4(self.colors[col])

                            uv = bs.readUShort()

                            if bHasUV2:
                                uv2 = bs.readUShort()
                                rapi.immLMUV2(self.uvs[uv2])

                            rapi.immUV2(self.uvs[uv])

                            if bUseCompBuffer:
                                rapi.immBoneIndex(self.boneIdx[vert])
                                rapi.immBoneWeight(self.boneWei[vert])
                                rapi.immNormal3(self.compNorm[norm])
                                rapi.immVertex3(self.compPos[vert])
                            else:
                                rapi.immNormal3(self.norm[norm])
                                rapi.immVertex3(self.pos[vert])

                    except IndexError:
                        print(">> {:#x}".format(bs.tell()))
                        raise
                        
                    rapi.immEnd()

            rapi.rpgOptimize()
            mdl = rapi.rpgConstructModel()
            mdl.setBones(self.bones)
            mdl.setModelMaterials(self.noeMaterials)
            self.mdlList.append(mdl)
