# Fatal Frame 4 rsl plugin by Zheneq
# For now, vertices only
# https://github.com/Zheneq/Noesis-Plugins

from inc_noesis import *
import noesis
import rapi
import os

debug = 1

#registerNoesisTypes is called by Noesis to allow the script to register formats.
#Do not implement this function in script files unless you want them to be dedicated format modules!
def registerNoesisTypes():
	handle = noesis.register("Fatal Frame 4 Archive", ".rsl")
	noesis.setHandlerTypeCheck(handle, noepyCheckType)
	noesis.setHandlerLoadModel(handle, noepyLoadModel)

	noesis.logPopup()
	return 1

#check if it's this type based on the data
def noepyCheckType(data):
	return RSLFile(NoeBitStream(data)).check()

#load the model
def noepyLoadModel(data, mdlList):
	RSLFile(NoeBitStream(data), mdlList).load()
	return len(mdlList)

class RSLFile:
	def __init__(self, bs, mdlList = None):
		self.bs = bs
		self.mdlList = mdlList
		self.root = None

	def check(self):
		return RMHG(self.bs, []).loadHeader()

	def load(self):
		self.root = RMHG(self.bs, self.mdlList)
		self.root.load()

		if debug:
			print("Structure:\nRoot")
			self.root.printStructure()


class RMHG:
	def __init__(self, bs, mdlList):
		self.bs = bs
		self.mdlList = mdlList
		self.records = []
		self.children = []

		self.parsers = {
			'RMHG': RMHG,
			'CGMG': CGMG,
		}

	def printStructure(self, prefix = ""):
		for x in self.records:
			print(prefix, x['type'], "0x{:x} bytes".format(x['size']))
			if x['type'] == "RMHG" and 'data' in x:
				x['data'].printStructure("\t" + prefix)

	def loadHeader(self):
		bs = self.bs
		bs.seek(0)

		magic = bs.readBytes(4).decode("ascii")
		if magic != "RMHG":
			return 0

		count = bs.readUInt()
		headerDataAddr = bs.readUInt()
		unk2 = bs.readUInt()
		dataSize = bs.readUInt() # ?

		bs.seek(headerDataAddr)
		self.records = [{
				'addr': bs.readUInt(),
				'size': bs.readUInt(),
				'unk': [bs.readUInt() for j in range(6)]
			} for i in range(count)]

		if not self.records and not dataSize:
			return 1
		if self.records[-1]['addr'] + self.records[-1]['size'] == dataSize and dataSize <= bs.getSize():
			return 1

	def load(self):
		bs = self.bs
		self.loadHeader()
		temp = 0
		for x in self.records:
			bs.seek(x['addr'])
			x['type'] = bs.readBytes(4).decode("ascii")
			if not x['addr'] or not x['size']:
				print("Empty", x['type'])
			elif x['type'] in self.parsers:
				if temp > 1: continue
				subBs = NoeBitStream(bs.getBuffer(x['addr'], x['addr'] + x['size']))
				x['data'] = self.parsers[x['type']](subBs, self.mdlList)
				x['data'].load()
				temp += 1
			else:
				print("Cannot parse", x['type'])



class CGMG:
	def __init__(self, bs, mdlList):
		self.bs = bs
		bs.setEndian(NOE_BIGENDIAN)
		self.mdlList = mdlList

	def load(self):
		bs = self.bs
		bs.seek(4)

		header = {
			'unk1': [bs.readUInt() for i in range(5)],
			'boneCount': bs.readUShort(),
			'unk2': [bs.readUShort() for i in range(3)],
			'skelAddr': bs.readUInt(),
			'skelSize': bs.readUInt(),
			'unk3': [bs.readUInt() for i in range(4)],
			'name': bs.readString()
		}
		print("header", header)

		bs.seek(header['skelAddr'])
		bones = []
		for i in range(header['boneCount']):
			bones.append({
				'name': bs.readBytes(8).decode("ascii").split('\0')[0],
				'some': bs.readUInt(),
				'meshDataDescAddr': bs.readUInt(),
				'unk1': [bs.readUInt() for j in range(4)],
				'meshHeaderAddr': bs.readUInt(),
				'unk2': [bs.readUInt() for j in range(2)],
				'pos': NoeVec3([bs.readFloat() for j in range(3)]),
				'rot': NoeVec3([bs.readFloat() for j in range(3)]),
				'scl': NoeVec3([bs.readFloat() for j in range(3)]),
				'unk3': [bs.readFloat() for j in range(6)],
				'unk4': bs.readUInt(),
				'meshAddr': bs.readUInt(),
				'unk5': [bs.readUInt() for j in range(4)],
			})

		meshes = []
		for b in bones:
			try:
				if (b['meshDataDescAddr']):
					bs.seek(b['meshDataDescAddr'])
					next = bs.readUInt()
					vertAddr = bs.readUInt()
					bs.seek(next + 4)
					vertCount = int((bs.readUInt() - vertAddr) / 12)

					if vertCount <= 0: continue

					bs.seek(vertAddr)
					verts = [NoeVec3([bs.readFloat() for j in range(3)]) for i in range(vertCount)]
					meshes.append(NoeMesh([], verts))
			except:
				continue

		self.mdlList.extend([NoeModel([m]) for m in meshes])
