# MegamanX8 wsx plugin by Zheneq
# https://github.com/Zheneq/Noesis-Plugins

from inc_noesis import *
import noesis
import rapi
import os
from collections import OrderedDict
from fmt_mmx8_wpg import WPGFile

def readQuat(bs):
    r = NoeAngles.fromBytes(bs.readBytes(12))
    r[0], r[1], r[2] = -r[0], r[2], r[1]
    return r.toQuat()

def registerNoesisTypes():
    # return 1
    handle = noesis.register("MegamanX8 Model", ".wsx")
    noesis.setHandlerTypeCheck(handle, noepyCheckType)
    noesis.setHandlerLoadModel(handle, noepyLoadModel)

    # noesis.logPopup()
    return 1

#check if it's this type based on the data
def noepyCheckType(data):
    wsx = WSXFile(NoeBitStream(data))
    return wsx.checkType()

#load the model
def noepyLoadModel(data, mdlList):
    if noesis.NOESIS_PLUGINAPI_VERSION < 73:
        noesis.messagePrompt("This plugin requires Noesis v4.2 or higher.")
        return 0
    wsx = WSXFile(NoeBitStream(data))
    return wsx.load(mdlList)


BLOCKHEADERSIZE = 60


class WSXFile:
    def __init__(self, bs):
        self.bs = bs
        self.blockTypes = [
            "Skeletal mesh",
            "Static mesh",
            "UNKNWN (2)",
            "Animations",
            "Material",
            "Material animations [not parsed]",
            "UNKNWN (6)"
        ]
        self.blockHandlers = [
            self.parseBlockMesh,
            self.parseBlockMesh,
            lambda h: 0,
            self.parseBlockAnim,
            self.parseBlockMat,
            lambda h: 0,
            lambda h: 0
        ]

        self.valid = False

        self.objects = OrderedDict()

    def checkType(self):
        bs = self.bs
        bs.seek(0)

        self.valid = False

        if bs.dataSize < 8:
            return 0

        bs.seek(4)
        FileSize = bs.readInt() + bs.readInt() # dataSize + shifts[0]

        if FileSize != bs.dataSize:
            return 0

        self.valid = True
        return 1

    def load(self, mdlList):
        # Check validity
        self.checkType()
        if not self.valid:
            return 0

        # Reset variables
        bs = self.bs
        bs.seek(0)

        # Header
        numRecords = bs.readInt()
        dataSize = bs.readInt()

        print("Loading {0} blocks ({1} bytes)".format(numRecords, dataSize))

        self.blockShifts = [bs.readInt() for i in range(numRecords)]
        fileSize = self.blockShifts[0] + dataSize
        self.blockShifts.append(fileSize)

        # Main loop
        for i in range(numRecords):
            self.parseBlock(i)

        #if matName is not None:
        #    wmesh.mesh.setMaterial(matName)

        # Sending to Noesis
        print("===== STATS =====")
        for obj in self.objects:
            mdl = NoeModel([], [], [])
            mdl.setMeshes(self.objects[obj].get('meshes', []))
            mdl.setBones(self.objects[obj].get('bones', []))
            mdl.setAnims(self.objects[obj].get('anims', []))
            mdl.setModelMaterials(NoeModelMaterials(self.objects[obj].get('textures', []), self.objects[obj].get('materials', [])))
            mdl.name = obj
            mdlList.append(mdl)

            print("{0}:".format(obj))
            print("\tMeshes:    {0}".format(len(mdl.meshes)))
            print("\tBones:     {0}".format(len(mdl.bones)))
            print("\tAnims:     {0}".format(len(mdl.anims)))
            print("\tTextures:  {0}".format(len(self.objects[obj].get('textures', []))))

        return 1

    def parseBlock(self, idx):
        bs = self.bs

        bs.seek(self.blockShifts[idx], NOESEEK_ABS)

        # Magic Number
        if bs.readInt() != 0x0101006c:
            print("bad record header", idx)
            return 0

        blockHeader = {
            'recordname': bs.readBytes(16).decode("ascii").split('\0')[0],
            'junk':       bs.readInt(),
            'recordtype': bs.readInt(),
            'recordinfo': [bs.readInt(), bs.readInt(), bs.readInt()],
            'objectname': bs.readBytes(16).decode("ascii").split('\0')[0],
            'shift':      self.blockShifts[idx]
        }

        print("{id:03}\t{blockname:<16}\t\t@ 0x{address:04X}\t(0x{size:X} bytes)\t({blocktype} for {objectname})".format(
            id=idx,
            blocktype=self.blockTypes[blockHeader['recordtype']],
            blockname=blockHeader['recordname'],
            objectname=blockHeader['objectname'],
            address=blockHeader['shift'],
            size=self.blockShifts[idx+1]-self.blockShifts[idx]
        ))

        # Create object if it does not exist
        if blockHeader['objectname'] not in self.objects:
            self.objects[blockHeader['objectname']] = {}

        # Reset shift (all pointers inside a block are relative to this shift)
        bs.seek(self.blockShifts[idx], NOESEEK_ABS)

        isParsed = self.blockHandlers[blockHeader['recordtype']](blockHeader)

    def parseBlockMesh(self, blockHeader):
        bs = self.bs
        bs.seek(BLOCKHEADERSIZE, NOESEEK_REL)

        # todo: unknown data
        print(bs.readInt(), bs.readInt())

        # boneCount
        boneCount = bs.readShort()
        if boneCount == 0:
            return

        # todo: unknown data
        t = bs.readShort()

        shifts = {
            'bones':    bs.readInt(),
            'junk':     bs.readInt(),
            's1':       bs.readInt(), # almost always boneCount * 64 bytes (almost == static/skeletal?)
            's2':       bs.readInt(), # meshCount * 18 bytes
            'boneInfo': bs.readInt(),
            's4':       bs.readInt(), # not always 0 bytes (int8)
            'junk':     bs.readInt(),
            'm1':       bs.readInt(), # 32 bytes
            'meshInfo': bs.readInt()
        }

        ################################## BONES ##################################
        # Reading bones
        bs.seek(blockHeader['shift'] + shifts['bones'], NOESEEK_ABS)
        bones = []
        for y in range(boneCount):
            p = {
                'rot':   NoeAngles.fromBytes(bs.readBytes(12)),
                'trans': NoeVec3.fromBytes(bs.readBytes(12)),
                'scale': NoeVec3.fromBytes(bs.readBytes(12))
            }
            p['rot'][0], p['rot'][1], p['rot'][2] = -p['rot'][0], p['rot'][2], p['rot'][1]
            bones.append(p)

        # Reading bone hierarchy
        bs.seek(blockHeader['shift'] + shifts['boneInfo'], NOESEEK_ABS)
        boneInfo = []
        for j in range(boneCount):
            t0 = [bs.readByte() for x in range(6)] # parent, 255 for 1st | 0 otherwise, bone index, ? some index , 0, 0

            boneInfo.append({"parent": t0[0], "index": t0[2], "other": t0[3]})

        # Building bones
        boneMatrices = []
        socketIndex = 0
        for j in range(boneCount):
            trans = NoeMat43().translate(bones[j]['trans'])
            rot = NoeMat43()
            scale = NoeMat43()

            if boneInfo[j]["parent"] != -1:
                rot = bones[boneInfo[j]["parent"]]['rot'].toMat43()
                scale = (NoeVec3((bones[j]['scale'][0], 0.0, 0.0)), NoeVec3((0.0, bones[j]['scale'][1], 0.0)),
                     NoeVec3((0.0, 0.0, bones[j]['scale'][2])), NoeVec3((0.0, 0.0, 0.0)))

            if boneInfo[j]["index"] != -1:
                boneInfo[j]["name"] = "bone{0:03}".format(boneInfo[j]["index"])
            else:
                boneInfo[j]["name"] = "socket{0:03}".format(socketIndex)
                socketIndex += 1

            bone = trans * scale * rot
            boneMatrices.append(bone)

        noeBones = [NoeBone(j, boneInfo[j]["name"], boneMatrices[j], parentIndex=boneInfo[j]["parent"])
                      for j in range(boneCount)]

        noeBones = rapi.multiplyBones(noeBones)
        for j in range(boneCount):
            noeBones[j].setMatrix(bones[j]['rot'].toMat43() * noeBones[j].getMatrix())

        self.objects[blockHeader['objectname']]['bones'] = noeBones

        ################################# MESHES ##################################
        bs.seek(blockHeader['shift'] + shifts['meshInfo'], NOESEEK_ABS)
        meshCount = bs.readInt()
        totalVertexCount = bs.readInt()

        # todo: unknown data
        bs.seek(16, NOESEEK_REL)

        meshInfo = []
        meshBones = []
        for j in range(meshCount):
            meshInfo.append([bs.readInt() for k in range(8)])
            meshBones.append([bs.readShort() for k in range(32)])
        meshDataShift = bs.tell()

        # meshDataShift = blockHeader['shift'] + meshInfoShift + 24 + 96 * meshCount
        self.objects[blockHeader['objectname']]['meshes'] = []
        for j in range(meshCount):
            bs.seek(meshDataShift, NOESEEK_ABS)
            wmesh = WSXMesh(j, bs, boneInfo, meshInfo[j], meshBones[j], meshDataShift, blockHeader['recordtype'] == 0,
                            blockHeader['objectname'] + "_" + str(j))

            # todo: move this to mesh parser??
            matList = self.objects[blockHeader['objectname']].get('materials', [])
            try:
                wmesh.mesh.setMaterial(matList[meshInfo[j][0]].name)
            except IndexError:
                print("> Missing texture {0}".format(meshInfo[j][0]))

            self.objects[blockHeader['objectname']]['meshes'].append(wmesh.mesh)

        return 1

    def parseBlockAnim(self, blockHeader):
        bs = self.bs

        bs.seek(BLOCKHEADERSIZE, NOESEEK_REL)

        animsNum = bs.readInt()
        shift = bs.readInt()

        bs.seek(blockHeader['shift'] + shift)
        frameData = [
            {
                "fps":            bs.readInt(),  # always 24?
                "frameCount":     bs.readInt(),
                "boneCount":      bs.readInt(),
                "junk":           bs.readInt(),
                "animsInfoShift": bs.readInt(),
                "animsDataShift": bs.readInt()
             } for x in range(animsNum)]

        dataShifts = []
        for frame in frameData:
            bs.seek(blockHeader['shift'] + frame["animsInfoShift"])
            frame["animsInfo"] = [
                {"framesCount": {
                    "rot":   bs.readShort(),
                    "trans": bs.readShort(),
                    "scale": bs.readShort(),
                    "junk":  bs.readShort()
                },
                    "framesRotShift":   bs.readInt(),
                    "framesTransShift": bs.readInt(),
                    "framesScaleShift": bs.readInt()
                } for x in range(frame["boneCount"])]
            dataShifts.append(blockHeader['shift'] + frame["animsDataShift"])

            for bone in frame["animsInfo"]:
                bs.seek(blockHeader['shift'] + frame["animsDataShift"] + bone["framesRotShift"])
                bone["framesRot"] = [NoeKeyFramedValue(bs.readInt(), readQuat(bs))
                                     for x in range(bone["framesCount"]["rot"])]

                bs.seek(blockHeader['shift'] + frame["animsDataShift"] + bone["framesTransShift"])
                bone["framesTrans"] = [NoeKeyFramedValue(bs.readInt(), NoeVec3.fromBytes(bs.readBytes(12)))
                                       for x in range(bone["framesCount"]["trans"])]

                bs.seek(blockHeader['shift'] + frame["animsDataShift"] + bone["framesScaleShift"])
                bone["framesScale"] = [NoeKeyFramedValue(bs.readInt(), NoeVec3.fromBytes(bs.readBytes(12)))
                                       for x in range(bone["framesCount"]["scale"])]

        anims = []
        for i in range(len(frameData)):
            frame = frameData[i]

            animName = "anim_{0:03}".format(i)
            # todo: bones are not always there??
            animBones = self.objects[blockHeader['objectname']].get('bones', [])
            animFrameRate = .5 #float(frame["fps"])
            animNumFrames = frame["frameCount"]

            animKFBones = []

            if frame["boneCount"] != len(animBones):
                print("> Not parsed")
                continue

            for x in range(frame["boneCount"]):
                b = NoeKeyFramedBone(x)
                b.setRotation(frame["animsInfo"][x]["framesRot"])
                b.setTranslation(frame["animsInfo"][x]["framesTrans"])
                b.setScale(frame["animsInfo"][x]["framesScale"], noesis.NOEKF_SCALE_VECTOR_3)

                animKFBones.append(b)

            anims.append(NoeKeyFramedAnim(animName, animBones, animKFBones, animFrameRate))

        self.objects[blockHeader['objectname']]['anims'] = anims
        return 1

    def parseBlockMat(self, blockHeader):
        bs = self.bs

        if 'textures' not in self.objects[blockHeader['objectname']]:
            self.objects[blockHeader['objectname']]['textures'] = []
        if 'materials' not in self.objects[blockHeader['objectname']]:
            self.objects[blockHeader['objectname']]['materials'] = []

        if blockHeader['recordinfo'][0] == 0:
            texList = []
            matList = []
            materialData = {}

            bs.seek(BLOCKHEADERSIZE, NOESEEK_REL)

            materialData['count'] = bs.readInt()

            # todo: unknown data
            bs.seek(blockHeader['shift'] + 0x6c, NOESEEK_ABS)

            # todo: recheck this
            TextureMapping = [{'shift': bs.readInt() & 0xFFFFFF, 'size': bs.readInt() & 0xFFFFFF}  # int24 lolwat?
                              for x in range(materialData['count'])]
            materialData['mapping'] = TextureMapping

            TextureStrings = [bs.readBytes(256).decode("ascii").split('\0', 1)[0] for x in range(4)] # [2] & [3] always empty
            if TextureStrings[0] != "wsxwpg":
                print("\t\tWSXWPG magic code is wrong!")
                return 0

            # loading textures
            materialData['name'] = TextureStrings[1]
            dirPath = rapi.getDirForFilePath(rapi.getInputName())
            texPath = os.path.join(dirPath, "wpg", TextureStrings[1])
            WPGFile(texList, blockHeader['objectname'], materialData['mapping'], texPath).load()
            for t in texList:
                matList.append(NoeMaterial(t.name, t.name))

            self.objects[blockHeader['objectname']]['textures'].extend(texList)
            self.objects[blockHeader['objectname']]['materials'].extend(matList)

            return 1
        elif blockHeader['recordinfo'][0] == -1:
            bs.seek(BLOCKHEADERSIZE, NOESEEK_REL)

            pattern = [bs.readInt() for i in range(12)]
            if pattern == [0, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]:
                # todo: not sure about this part
                return 0
                # use legacy
                # crashes when this is the first block of the file
                source = list(self.objects.items())[-2][1]
                self.objects[blockHeader['objectname']]['textures'].extend(source['textures'])
                self.objects[blockHeader['objectname']]['materials'].extend(source['materials'])

                return 1

        return 0


class WSXMesh:
    def __init__(self, index, bs, boneInfo, meshInfo, meshBones, meshDataShift, bSkeletal, meshName):
        VertexLen = 9
        if bSkeletal:
            VertexLen = 15
        dcType = meshInfo[1] # triangles / triangle strip
        vertexCount = meshInfo[2]
        dcShift = meshInfo[3] * 4 * VertexLen

        # print("\t\t\tMesh {0:02}, {1} vertices, type {2}".format(index, vertexCount, dcType))
        # print(meshInfo)
        # print("bones: ", meshBones)
        # break

        self.mesh = NoeMesh([], [], meshName)
        if dcType == 0:
            # TRIANGLES
            self.mesh.indices = [x for x in range(vertexCount)]
        elif dcType == 1:
            # TRIANGLE_STRIP
            for x in range(0, vertexCount - 4, 2):
                self.mesh.indices.extend([x, x+1, x+2, x+2, x+1, x+3])
        else:
            print("=============================================")


        bs.seek(dcShift, NOESEEK_REL)

        for x in range(vertexCount):
            self.mesh.positions.append(NoeVec3.fromBytes(bs.readBytes(12)))
            self.mesh.normals.append(NoeVec3.fromBytes(bs.readBytes(12)))
            self.mesh.uvs.append(NoeVec3.fromBytes(bs.readBytes(12)))  # junk, u, v
            self.mesh.uvs[-1][0], self.mesh.uvs[-1][1], self.mesh.uvs[-1][2] = \
                self.mesh.uvs[-1][1], self.mesh.uvs[-1][2], self.mesh.uvs[-1][0]  # u, v, junk
            if bSkeletal:
                boneWeights = [bs.readFloat() for y in range(3)]
                vertexColor = NoeVec3.fromBytes(bs.readBytes(12))

                boneIndices = []
                boneLocalIndices = [meshBones[int(y/3)-1] for y in vertexColor]
                for y in boneLocalIndices:
                    for z in range(len(boneInfo)):
                        if boneInfo[z]["index"] == y:
                            boneIndices.append(z)
                            break
                    else:
                        print("bone data is corrupt (bone {0} not found)".format(y))

                #print("boneWeights", boneWeights)
                #print("vertexColor", vertexColor)
                #print("vertexColorIdx", [int(y/3)-1 for y in vertexColor])
                #print("boneLocalIndices", boneLocalIndices)
                #print("boneIndices", boneIndices)
                #print()

                self.mesh.weights.append(NoeVertWeight(boneIndices, boneWeights))
            else:
                self.mesh.weights.append(NoeVertWeight([meshBones[0]], [1.0]))