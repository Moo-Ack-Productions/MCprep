
########
"""
This code is open source under the MIT license.

Its purpose is to increase the workflow of creating Minecraft
related renders and animations, by automating certain tasks.

This addon for blender functions by operating on selected objects,
which are expected to be Minecraft worlds exported from the game
using the jMC2Obj program. Use on meshes not originating from there
may have unexpected behavior or unwanted changes to materials.

Source code available on github:
https://github.com/TheDuckCow/MCprep.git

WIP thread on blenderartists:
http://www.blenderartists.org/forum/showthread.php?316151-ADDON-WIP-MCprep-for-Minecraft-Workflow

# KNOWN BUGS:
-	if multiple objects with same material mesh swapped in one go
	>> easy work around would be to auto join them together, but should be error'd...
-	not all replacements for standard block replacements work, extra blocks appear
-	sometimes cannot meshswap a second time if done once in a scene already, e.g. vine
	appears to be due to stale, or kept data between op runs.
-	Sometimes mesh swap will not run if the MESH (not OBJECT) name is competely wrong
"""

########
bl_info = {
	"name": "MCprep",
	"category": "Object",
	"version": (1, 3, 0),
	"blender": (2, 72, 0),
	"location": "3D window toolshelf",
	"description": "Speeds up the workflow of minecraft animations and imported minecraft worlds",
	"warning": "",
	"wiki_url": "https://github.com/TheDuckCow/MCprep.wiki.git",
	"author": "Patrick W. Crawford"
}

import bpy,os,mathutils,random,math


########################################################################################
#	Below for precursor functions
#	Thereafter for the class functions
########################################################################################


########
# Get the lists of either hard coded or library parsed lists for functions
# this should be a dictionary, not a function! can update fairly easily, track references..
# but like fo serious, make this a dictionary object with lists....
def getListData():
	
	# ideally in long run, will do check for specific names of materials/existing
	# groups in the assets file.
	
	
	# lists for material prep
	reflective = [ 'glass', 'glass_pane_side','ice']
	water = ['water','water_flowing']
	solid = ['sand','dirt','dirt_grass_side','dispenser_front','furnace_top','redstone_block',
				'gold_block','yourFace']
	emit= ['redstone_block','redstone_lamp_on','glowstone','lava','lava_flowing']
	
	# lists for meshSwap
	## groupSwapList has a higher precedence;
	## if same object type is in both group and mesh swap list, group will be used
	groupSwapList = ['redstone_torch_on','redstone_lamp_on','torch','endercrystal','fire']
	meshSwapList = ['tall_grass','flower_red','flower_yellow','cobweb','redstone_torch_on',
					'redstone_lamp_off','dead_shrub','sapling_oak','redstone_wire_off',
					'wheat','redstone_torch_off','rails','rails_powered_off','ladder',
					'mushroom_red','mushroom_brown','vines','lilypad','azure',
					'stained_clay_brown','stained_clay_dark_gray','dirt',
					'double_plant_grass_bottom','cobweb']
	# blocks perfectly on edges, require rotation	
	edgeFlush = [] 	
	# blocks floating off edge into air, require rotation
	edgeFloat = ['vines','ladder','lilypad']
	torchlike = ['torch','redstone_torch_on','redstone_torch_off']
	#remove meshes not used for processing, for objects imported with extra meshes
	removable = ['double_plant_grass_top','torch_flame']
	
	# for varied positions from exactly center on the block, 1 for Z random too
	variance = [ ['tall_grass',1], ['double_plant_grass_bottom',1],
				['flower_yellow',0], ['flower_red',0] ]
	
	########
	
	#attempt to LOAD information from an asset file...
	meshSwapPath = bpy.context.scene.MCprep_meshswap_path
	if not(os.path.isfile(meshSwapPath)):
		#extract actual path from the relative one
		meshSwapPath = bpy.path.abspath(meshSwapPath)
	
	
	#print("#: ",meshSwapPath)
	
	#####
	
	
	return {'meshSwapList':meshSwapList, 'groupSwapList':groupSwapList,
			'reflective':reflective, 'water':water, 'solid':solid,
			'emit':emit, 'variance':variance, 'edgeFlush':edgeFlush,
			'edgeFloat':edgeFloat,'torchlike':torchlike,'removable':removable}



########
# add object instance not working, so workaround function:
def addGroupInstance(groupName,loc):
	scene = bpy.context.scene
	ob = bpy.data.objects.new(groupName, None)
	ob.dupli_type = 'GROUP'
	ob.dupli_group = bpy.data.groups.get(groupName)
	ob.location = loc
	scene.objects.link(ob)
	ob.select = True


########
# check if a face is on the boundary between two blocks (local coordinates)
def onEdge(faceLoc):
	strLoc = [ str(faceLoc[0]).split('.')[1][0],
				str(faceLoc[1]).split('.')[1][0],
				str(faceLoc[2]).split('.')[1][0] ]
	if (strLoc[0] == '5' or strLoc[1] == '5' or strLoc[2] == '5'):
		return True
	else:
		return False


########
# randomization for model imports, add extra statements for exta cases
def randomizeMeshSawp(swap,variations):
	randi=''
	if swap == 'torch':
		randomized = random.randint(0,variations-1)
		#print("## "+str(randomized))
		if randomized != 0: randi = ".{x}".format(x=randomized)
	return swap+randi


########
# strips out duplication naming ".001", ".002" from a name
def nameGeneralize(name):
	nameList = name.split(".")
	#check last item in list, to see if numeric type e.g. from .001
	try:
		x = int(nameList[-1])
		name = nameList[0]
		for a in nameList[1:-1]: name+='.'+a
	except:
		pass
	return name


########
# gets all materials on input list of objects
def getObjectMaterials(objList):
	matList = []
	
	#loop over every object, adding each material if not alraedy added
	for obj in objList:
		#must be a mesh, e.g. lamps or cameras don't have 'materials'
		if obj.type != 'MESH': continue
		
		objectsMaterials = obj.material_slots
		for materialID in objectsMaterials:
			if materialID.material not in matList:
				matList.append(materialID.material)
	
	return matList


########
# gets all textures on input list of materials
# currently not used, some issue in getting NoneTypes (line if textureID.texture in..)
def getMaterialTextures(matList):
	if len(matList)==0: return []
	texList = []
	
	# loop over every material, adding each texture slot
	for mat in matList:
		materialTextures = mat.texture_slots
		#print("###",materialTextures)
		if len(materialTextures)==0: return []
		for textureID in materialTextures:
			if textureID.texture not in texList:
				texList.append(textureID.texture)
	
	return texList


########
# For multiple version compatibility,
# this function generalized appending/linking
def bAppendLink(directory,name, toLink):
	# blender post 2.71 changed to new append/link methods
	version = bpy.data.version
	
	if (version[0] >= 2 and version[1] >= 72):
		# NEW method of importing
		if (toLink):
			bpy.ops.wm.link(directory=directory, filename=name)
		else:
			bpy.ops.wm.append(directory=directory, filename=name)
	else:
		# OLD method of importing
		bpy.ops.wm.link_append(directory=directory, filename=name, link=toLink)
	




########################################################################################
#	Above for precursor functions
#	Below for the class functions
########################################################################################

########
# Operator, sets up the materials for better Blender Internal rendering
class materialChange(bpy.types.Operator):
	"""Preps selected minecraft materials"""
	bl_idname = "object.mc_mat_change"
	bl_label = "MCprep mats"
	bl_options = {'REGISTER', 'UNDO'}
	
	
	## HERE functions for GENERAL material setup (cycles and BI)
	def materialsInternal(self, mat):
		
		# defines lists for materials with special default settings.
		listData = getListData()
		
		try:
			newName = mat.name+'_tex' # add exception to skip? with warning?
			texList = mat.texture_slots.values()
		except:
			print('\tissue: '+obj.name+' has no active material')
			return
	   
		### Check material texture exists and set name
		try:
			#if bpy.data.textures[texList[0].name].filter_type == 'BOX':
			#	return #to skip non pre-prepped mats, but shouldn't need to...
			bpy.data.textures[texList[0].name].name = newName
		except:
			print('\tiwarning: material '+mat.name+' has no texture slot. skipping...')
			return

		# disable all but first slot, ensure first slot enabled
		mat.use_textures[0] = True
		for index in range(1,len(texList)):
			mat.use_textures[index] = False
	   
		#generalizing the name, so that lava.001 material is recognized and given emit
		matGen = nameGeneralize(mat.name)
	   
		mat.use_transparent_shadows = True #all materials receive trans
		mat.specular_intensity = 0
		mat.texture_slots[0].texture.use_interpolation = False
		mat.texture_slots[0].texture.filter_type = 'BOX'
		mat.texture_slots[0].texture.filter_size = 0
		mat.texture_slots[0].use_map_color_diffuse = True
		mat.texture_slots[0].diffuse_color_factor = 1
		mat.use_textures[1] = False

		if not matGen in listData['solid']: #ie alpha is on unless turned off
			bpy.data.textures[newName].use_alpha = True
			mat.texture_slots[0].use_map_alpha = True
			mat.use_transparency = True
			mat.alpha = 0
			mat.texture_slots[0].alpha_factor = 1
		   
		if matGen in listData['reflective']:
			mat.alpha=0.3
			mat.raytrace_mirror.use = True
			mat.raytrace_mirror.reflect_factor = 0.3
	   
		if matGen in listData['emit']:
			mat.emit = 1
		else:
			mat.emit = 0
	
	### Function for default cycles materials
	def materialsCycles(self, mat):
		
		# defines lists for materials with special default settings.
		listData = getListData()
		
		# generalize name
		matGen = nameGeneralize(mat.name)
		
		#enable nodes
		
		#set nodes
		
		#warning that nothing done to scale textures, must just use scaled
		#up textures to look proper!
	
	### HERE function for linking/appending from asset scene
	
	def execute(self, context):
		
		#get list of selected objects
		objList = context.selected_objects

		# gets the list of materials (without repetition) in the selected object list
		matList = getObjectMaterials(objList)
		
		for mat in matList:
			#check if linked material exists
			render_engine = bpy.context.scene.render.engine
			
			#if linked false:
			if (True):
				if (render_engine == 'BLENDER_RENDER'):
					#print('BI mat')
					self.materialsInternal(mat)
				elif (render_engine == 'CYCLES'):
					#print('cycles mat')
					self.materialsCycles(mat)
			else:
				print('Get the linked material instead!')

		return {'FINISHED'}



########
# Operator, funtion swaps meshes/groups from library file
class meshSwap(bpy.types.Operator):
	"""Swap minecraft imports for custom 3D models in the meshSwap blend file"""
	bl_idname = "object.mc_meshswap"
	bl_label = "MCprep meshSwap"
	bl_options = {'REGISTER', 'UNDO'}
	
	#move things out of here!
	
	#used for only occasionally refreshing the 3D scene while mesh swapping
	counterObject = 0	# used in count
	countMax = 5		# count compared to this, frequency of refresh (number of objs)
	
	def execute(self, context):
		
		## debug, restart check
		print('###################################')
		
		# get some scene information
		toLink = context.scene.MCprep_linkGroup
		groupAppendLayer = context.scene.MCprep_groupAppendLayer
		activeLayers = list(context.scene.layers)
		
		#separate each material into a separate object
		selList = context.selected_objects
		for obj in selList:
			bpy.ops.mesh.separate(type='MATERIAL')
		
		# now do type checking and fix any name discrepencies
		selList = context.selected_objects
		objList = []
		for obj in selList:
			#ignore non mesh selected objects
			if obj.type != 'MESH': continue
			
			prevName = obj.name
			try:bpy.data.meshes[prevName].name = obj.active_material.name
			except: continue
			obj.name = obj.active_material.name
			bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
			objList.append(obj.name)
			print(obj.name)
		
			
		# get library path from property/UI panel
		direc = context.scene.MCprep_meshswap_path
		if not(os.path.isdir(direc)):
			#extract actual path from the relative one
			direc = bpy.path.abspath(direc)

		#print(direc)
		if not os.path.exists(direc):
			print('meshSwap asset not found! Check/set library path')

			#bpy.ops.object.dialogue('INVOKE_DEFAULT') # DOES work!
			self.report({'ERROR'}, "Mesh swap blend file not found!") # better, actual "error"
			return {'CANCELLED'}
		
		
		# Now get a list of all objects in this blend file, and all groups
		listData = getListData()
		#first go through and separate materials/faces of specific one into one mesh. I've got
		# that already, so moving on.
		### HERE use equivalent of UI "p" ? seperate by materials
		
		# for each object in objList: bpy.ops.mesh.separate(type='MATERIAL')
		
		#primary loop, for each OBJECT needing swapping
		for swap in objList:
			
			#first check if swap has already happened:
			# generalize name to do work on duplicated meshes, but keep original
			swapGen = nameGeneralize(swap)
			
			#special cases, for "extra" mesh pieces we don't want around afterwards
			#get rid of: special case e.g. blocks with different material sides,
			#only use swap based on one material object and delete the others
			if swapGen in listData['removable']: #make sure torch is one of the imported groups!
				bpy.ops.object.select_all(action='DESELECT')
				bpy.data.objects[swap].select = True
				bpy.ops.object.delete()
				continue
			
			
			#just selecting mesh with same name accordinly.. ALSO only if in objList
			if not (swapGen in listData['meshSwapList'] or swapGen in listData['groupSwapList']): continue		
			
			#now you have object that has just that material. Known.
			toSwapObj = bpy.data.objects[swap] #the object that would be created above...
			
			#procedurally getting the "mesh" from the object, instead of assuming name..
			#objSwapList =	// rawr. meshes not accessible through the object. huh.
			objSwapList = bpy.data.meshes[swap] #the mesh that would be created above...
			
			worldMatrix = toSwapObj.matrix_world.copy() #set once per object
			polyList = objSwapList.polygons.values() #returns LIST of faces.
			#print(len(polyList)) # DON'T USE POLYLIST AFTER AFFECTING THE MESH
			for poly in range(len(polyList)):
				objSwapList.polygons[poly].select = False
			
			#loop through each face or "polygon" of mesh
			facebook = [] #what? it's where I store the information of the obj's faces..
			for polyIndex in range(0,len(polyList)):
				gtmp = toSwapObj.matrix_world*mathutils.Vector(objSwapList.polygons[polyIndex].center)
				g = [gtmp[0],gtmp[1],gtmp[2]]
				n = objSwapList.polygons[polyIndex].normal #currently not used!
				tmp2 = objSwapList.polygons[polyIndex].center
				l = [tmp2[0],tmp2[1],tmp2[2]] #to make value unlinked to mesh
				facebook.append([n,g,l]) # g is global, l is local
			
			# NOTE, I did comparison test: the above code IS fine, 
			# same result for partially successful and completely unsuccessful trials
			
			bpy.ops.object.select_all(action='DESELECT')

			"""
			
			August 4, 2014 - 1:51 am
			R.I.P. the bug that plagued my aniamtions since the dawn of this addon.
			
			This bug lived a long life, it went many places - and saw many imported worlds.
			And while it may have seemed to exist soley for the purpose of my demise, it was
			a test of my character, and through it I have grown stronger and wiser.
			
			The original line, which caused this issue that needed only commenting out to fix:
				
				bpy.ops.object.delete() #Hey! The values of facebook are unchanged, so it's NOT linked..?
			
			Note how I had even questioned the deletion of this object when first written, but found it
			strange that the values linked to it remained unchanged given the objects absence.
			
			As I now understand, blender has an internal memory garbage collector, and sometimes it
			takes shorter or longer for deleted obejct data to be removed from the gargage. And hence,
			the variance in being how long it took before the meshSwap object ob.worldMatrix many
			lines hereafter would go awry, for at the point where meshes began to transoform in odd
			ways, the original object had finally, and truly, been removed.
			
			Also, note to self: this function is still a hell of a mess. Do something about it.
			
			"""
			
			### NOTE: NAMING ISSUES: IF there already was another mesh of the same name before importing,
			### the imported mesh REPLACES the old one. That's a problem. except in my special case.
			### perhaps just programatically change the name here
			
			# removing duplicates and checking orientation
			dupList = []	#where actual blocks are to be added
			rotList = []	#rotation of blocks
			
			for setNum in range(0,len(facebook)):
				
				# LOCAL coordinates!!!
				x = round(facebook[setNum][2][0]) #since center's are half ints.. 
				y = round(facebook[setNum][2][1]) #don't need (+0.5) -.5 structure
				z = round(facebook[setNum][2][2])
				
				
				# UNCOMMENT THE FOLLOWING LINES TO MAKE ROTATION THINGS WORK AGAIN
				outsideBool = -1
				if (swapGen in listData['edgeFloat']): outsideBool = 1
				
				if onEdge(facebook[setNum][2]): #check if face is on unit block boundary (local coord!)
					a = facebook[setNum][0][0] * 0.4 * outsideBool #x normal
					b = facebook[setNum][0][1] * 0.4 * outsideBool #y normal
					c = facebook[setNum][0][2] * 0.4 * outsideBool #z normal
					x = round(facebook[setNum][2][0]+a) 
					y = round(facebook[setNum][2][1]+b)
					z = round(facebook[setNum][2][2]+c)
					#print("ON EDGE, BRO! line ~468, "+str(x) +","+str(y)+","+str(z)+", ")
					#print([facebook[setNum][2][0], facebook[setNum][2][1], facebook[setNum][2][2]])
				
				# this HACK IS JUST FOR TORCHES... messes up things like redstone, lilypads..
				
				
				#### TORCHES
				if facebook[setNum][2][1]+0.5 - math.floor(facebook[setNum][2][1]+0.5) < 0.3:
					#continue if coord. is < 1/3 of block height, to do with torch's base in wrong cube.
					"""
					print("TORCH HACK? line ~473")
					if swapGen not in ['lilypad','redstone_wire_off']:
						continue
					"""
				print(" DUPLIST: ")
				print([x,y,z], [facebook[setNum][2][0], facebook[setNum][2][1], facebook[setNum][2][2]])
				
				# rotation value (second append value: 0 means nothing, rest 1-4.
				if (not [x,y,z] in dupList) or (swapGen in listData['edgeFloat']):
					# append location
					dupList.append([x,y,z])
					
					
					# check differece from rounding, this gets us the rotation!
					x_diff = x-facebook[setNum][2][0]
					#print(facebook[setNum][2][0],x,x_diff)
					z_diff = z-facebook[setNum][2][2]
					#print(facebook[setNum][2][2],z,z_diff)
					
					## rotations are handled on an object-to-object basis
					
					# append rotation
					if swapGen in ['torch','redstone_torch_off','redstone_torch_on']:
						if (x_diff>.2 and x_diff < 0.3):
							rotList.append(1)
						elif (z_diff>.2 and z_diff < 0.3):	
							rotList.append(2)
						elif (x_diff<-.2 and x_diff > -0.3):	
							rotList.append(3)
						elif (z_diff<-.2 and z_diff > -0.3):
							rotList.append(4)
						else:
							rotList.append(0)
					elif swapGen in listData['edgeFloat']:	# needs fixing
						if (y-facebook[setNum][2][1] < 0):
							rotList.append(8)
							#print('rotation ceiling')
						elif (x_diff > 0.3):
							rotList.append(7)
							#print('not to mention here!')
						elif (z_diff > 0.3):	
							rotList.append(0)
							#print('left here!')
						elif (z_diff < -0.3):
							rotList.append(6)
							#print('right here!') 
						else:
							rotList.append(5)
							#print('nothing to see here!')
					elif swapGen in listData['edgeFlush']:
						# actually 6 cases here, can need rotation below...
						# currently not necessary, so not programmed..  
						rotList.append(0)
					else:
						# no rotation from source file, must always append something
						rotList.append(0)
					
			#for a in dupList:print(a)
			
			#import: guaranteed to have same name as "appendObj" for the first instant afterwards
			grouped = False # used to check if to join or not
			base = None 	# need to initialize to something, though this obj no used
			if swapGen in listData['groupSwapList']:
				
				print(">> link group?",toLink,groupAppendLayer,swapGen)
				
				# GROUP LAYER APPENDING DOESN'T WORK CURRENTLY
				# if group not linked, put appended group data onto the GUI field layer
				if (not toLink) and (groupAppendLayer!=0):
					x = [False]*20
					x[groupAppendLayer-1] = True
					context.scene.layers = x
				
				#special cases, make another list for this? number of variants can vary..
				if swapGen == "torch":
					bAppendLink(direc+'/Group/', swapGen+".1", toLink)
					bpy.ops.object.delete()
					bAppendLink(direc+'/Group/', swapGen+".2", toLink)
					bpy.ops.object.delete()
				
				bAppendLink(direc+'/Group/', swapGen, toLink)
				
				bpy.ops.object.delete()
				grouped = True
				
				# if activated a different layer, go back to the original ones
				context.scene.layers = activeLayers
				
			else:
				
				bAppendLink(direc+'/Object/',swapGen, False)
				
				### NOTICE: IF THERE IS A DISCREPENCY BETWEEN ASSETS FILE AND WHAT IT SAYS SHOULD BE IN FILE
				### EG NAME OF MESH TO SWAP CHANGED,  INDEX ERROR IS THROWN HERE
				### >> MAKE a more graceful error indication.
				
				try:
					base = bpy.context.selected_objects[0]
				except:
					continue #in case nothing selected.. which happens even during selection?
				"""
				try:
					base = bpy.context.selected_objects[0]
					if base["MCprep_noSwap"] == "True":
						print("DID WE MAKE IT HERE")
						continue
				except:
					base["MCprep_noSwap"] = "True"
				"""
				bpy.ops.object.select_all(action='DESELECT')

			
			##### OPTION HERE TO SEGMENT INTO NEW FUNCTION
			print("### > trans")
			#self.counterObject = 0
			# duplicating, rotating and moving
			dupedObj = []
			for (set,rot) in zip(dupList,rotList):
				
				### HIGH COMPUTATION/CRITICAL SECTION
				#refresh the scene every once in awhile
				self.counterObject+=1
				if (self.counterObject > self.countMax):
					self.counterObject = 0
					#below technically a "hack", should use: bpy.data.scenes[0].update()
					bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

				
				loc = toSwapObj.matrix_world*mathutils.Vector(set) #local to global
				if grouped:
					# definition for randimization, defined at top!
					randGroup = randomizeMeshSawp(swapGen,3)
					
					# The built in method fails, bpy.ops.object.group_instance_add(...)
					#UPDATE: I reported the bug, and they fixed it nearly instantly =D
					# but it was recommended to do the below anyways.
					addGroupInstance(randGroup,loc)
					
				else:
					#sets location of current selection, imported object or group from above
					base.select = True		# select the base object
					bpy.ops.object.duplicate(linked=False, mode='TRANSLATION')
					bpy.context.selected_objects[-1].location = mathutils.Vector(loc) #hackish....
					dupedObj.append(bpy.context.selected_objects[-1])
					base.select = False
				
				obj = bpy.context.selected_objects[-1]	
				# do extra transformations now as necessary
				obj.rotation_euler = toSwapObj.rotation_euler
				# special case of un-applied, 90(+/- 0.01)-0-0 rotation on source (y-up conversion)
				if (toSwapObj.rotation_euler[0]>= math.pi/2-.01 and toSwapObj.rotation_euler[0]<= math.pi/2+.01
					and toSwapObj.rotation_euler[1]==0 and toSwapObj.rotation_euler[2]==0):
					obj.rotation_euler[0] -= math.pi/2
				obj.scale = toSwapObj.scale
				
				
				#rotation/translation for walls, assumes last added object still selected
				x,y,offset,rotValue,z = 0,0,0.28,0.436332,0.12
				
				if rot == 1:
					# torch rotation 1
					x = -offset
					obj.location += mathutils.Vector((x, y, z))
					#bpy.ops.transform.rotate(value=rotValue, axis=(0, 1, 0))
					obj.rotation_euler[1]+=rotValue
				elif rot == 2:
					# torch rotation 2
					y = offset
					obj.location += mathutils.Vector((x, y, z))
					#bpy.ops.transform.rotate(value=rotValue, axis=(1, 0, 0))
					obj.rotation_euler[0]+=rotValue
				elif rot == 3:
					# torch rotation 3
					x = offset
					obj.location += mathutils.Vector((x, y, z))
					#bpy.ops.transform.rotate(value=-rotValue, axis=(0, 1, 0))
					obj.rotation_euler[1]+=rotValue
				elif rot == 4:
					# torch rotation 4
					y = -offset
					obj.location += mathutils.Vector((x, y, z))
					#bpy.ops.transform.rotate(value=-rotValue, axis=(1, 0, 0))
					obj.rotation_euler[0]+=rotValue
				elif rot == 5:
					# edge block rotation 1
					#bpy.ops.transform.rotate(value=-math.pi/2,axis=(0,0,1))
					obj.rotation_euler[2]+= -math.pi/2
				elif rot == 6:
					# edge block rotation 2
					#bpy.ops.transform.rotate(value=math.pi,axis=(0,0,1))
					obj.rotation_euler[2]+= math.pi
				elif rot == 7:
					# edge block rotation 3
					#bpy.ops.transform.rotate(value=math.pi/2,axis=(0,0,1))
					obj.rotation_euler[2]+= math.pi/2
				elif rot==8:
					# edge block rotation 4 (ceiling, not 'keep same')
					#bpy.ops.transform.rotate(value=math.pi/2,axis=(1,0,0))
					obj.rotation_euler[0]+= math.pi/2
					
				# extra variance to break up regularity, e.g. for tall grass
				if [swapGen,1] in listData['variance']:
					x = (random.random()-0.5)*0.5
					y = (random.random()-0.5)*0.5
					z = (random.random()/2-0.5)*0.6 # restriction guarentees it will never go Up (+z value)
					obj.location += mathutils.Vector((x, y, z))
					
				elif [swapGen,0] in listData['variance']: # for non-z variance
					x = (random.random()-0.5)*0.5	 # values LOWER than *1.0 make it less variable
					y = (random.random()-0.5)*0.5
					obj.location += mathutils.Vector((x, y, 0))
				bpy.ops.object.select_all(action='DESELECT')
			
			
			### END CRITICAL SECTION
				
			if not grouped:
				base.select = True
				bpy.ops.object.delete() # the original copy used for duplication
			
			
			#join meshes together
			if not grouped and (len(dupedObj) >0):
				#print(len(dupedObj))
				# ERROR HERE if don't do the len(dupedObj) thing.
				bpy.context.scene.objects.active = dupedObj[0]
				for d in dupedObj:
					d.select = True
				
				bpy.ops.object.join()
			
			bpy.ops.object.select_all(action='DESELECT')
			toSwapObj.select = True
			bpy.ops.object.delete()
			
			#deselect? or try to reselect everything that was selected previoulsy
			bpy.ops.object.select_all(action='DESELECT')
		
		return {'FINISHED'}


#######
# Class for spawning/proxying a new asset for animation
class proxySpawn(bpy.types.Operator):
	"""Spawns in selected asset and proxies it ready for animation -- WIP"""
	bl_idname = "object.proxy_spawn"
	bl_label = "Proxy Spawn"
	bl_options = {'REGISTER', 'UNDO'}
	
	def execute(self, context):
		print("hello world")
		
		return {'FINISHED'}


#######
# Class for updating the duplicated proxy spawn files
class proxyUpdate(bpy.types.Operator):
	"""Updates all proxy spawn files to be consistent -- WIP"""
	bl_idname = "object.proxy_update"
	bl_label = "Proxy Update"
	bl_options = {'REGISTER', 'UNDO'}
	
	def execute(self, context):
		print("hello world")
		
		return {'FINISHED'}


#######
# pop-up declaring some button is WIP still =D
class WIP(bpy.types.Menu):
	bl_label = "wip_warning"
	bl_idname = "view3D.wip_warning"

	# Set the menu operators and draw functions
	def draw(self, context):
		layout = self.layout

		row1 = layout.row()
		row1.label(text="This addon is a work in progress, this function is not yet implemented")  


#######
# panel for these declared tools
class MCpanel(bpy.types.Panel):
	"""MCprep addon panel"""
	bl_label = "MCprep Panel"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'

	def draw(self, context):
		
		layout = self.layout
		split = layout.split()
		col = split.column(align=True)
		
		row = col.row(align=True)
		row.label(text="MeshSwap blend")
		row.prop(context.scene,"MCprep_meshswap_path",text="")
		
		row = col.row(align=True)
		row.label(text="Materials blend")
		row.prop(context.scene,"MCprep_material_path",text="")
		#does nothing yet (correctly)
		#col.prop(context.scene,"MCprep_groupAppendLayer",text="")
		
		split = layout.split()
		col = split.column(align=True)
		#for setting MC materials and looking in library
		col.operator("object.mc_mat_change", text="Prep Materials", icon='MATERIAL')
		#below should actually just call a popup window
		col.operator("object.mc_meshswap", text="Mesh Swap", icon='LINK_BLEND')
		
		split = layout.split()
		col = split.column(align=True)
		# doesn't properly work yet
		#col.label(text="Link groups")
		#col.prop(context.scene,"MCprep_linkGroup")



########################################################################################
#	Above for the class functions
#	Below for extra classes/registration stuff
########################################################################################


# WIP OK button general purpose
class dialogue(bpy.types.Operator):
	bl_idname = "object.dialogue"
	bl_label = "dialogue"
	message = "Library error, check path to assets has the meshSwap blend"
	
	def execute(self, context):
		self.report({'INFO'}, self.message)
		print(self.message)
		return {'FINISHED'}
	
	def invoke(self, context, event):
		wm = context.window_manager
		return wm.invoke_popup(self, width=400, height=200)
		#return wm.invoke_props_dialog(self)
	
	def draw(self, context):
		self.layout.label(self.message)

#######

def register():
	bpy.utils.register_class(materialChange)
	bpy.utils.register_class(meshSwap)
	bpy.utils.register_class(proxyUpdate)
	bpy.utils.register_class(proxySpawn)
	
	
	bpy.utils.register_class(dialogue)
	bpy.utils.register_class(WIP)
	bpy.utils.register_class(MCpanel)
	
	#properties
	bpy.types.Scene.MCprep_meshswap_path = bpy.props.StringProperty(
		name="Location of asset files",
		description="Locaiton of meshswapping assets",
		default="//asset_meshswap.blend",subtype="FILE_PATH")
	bpy.types.Scene.MCprep_material_path = bpy.props.StringProperty(
		name="Location of asset materials",
		description="Locaiton of materials for linking",
		default="//asset_materials.blend",subtype="FILE_PATH")
	bpy.types.Scene.MCprep_linkGroup = bpy.props.BoolProperty(
		name="Link library groups",
		description="Links groups imported, otherwise groups are appended",
		default=True)
	bpy.types.Scene.MCprep_groupAppendLayer = bpy.props.IntProperty(
		name="Group Append Layer",
		description="When groups are appended instead of linked, the objects part of the group will be palced in this layer, 0 means same as active layer, otherwise sets the the given layer number",
		min=0,
		max=20,
		default=20)


def unregister():
	bpy.utils.unregister_class(materialChange)
	bpy.utils.unregister_class(meshSwap)
	bpy.utils.unregister_class(proxyUpdate)
	bpy.utils.unregister_class(proxySpawn)
	
	bpy.utils.unregister_class(dialogue)
	bpy.utils.unregister_class(WIP)
	bpy.utils.unregister_class(MCpanel)
	
	#properties
	del bpy.types.Scene.MCprep_meshswap_path
	del bpy.types.Scene.MCprep_material_path
	del bpy.types.Scene.MCprep_linkGroup
	del bpy.types.Scene.MCprep_groupAppendLayer


if __name__ == "__main__":
	register()

