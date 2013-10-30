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

"""

########
bl_info = {
	"name": "MCprep",
	"category": "Object",
	"version": (0, 5),
	"blender": (2, 68, 2),
	"location": "3D window toolshelf",
	"description": "Speeds up the workflow of minecraft animations and imported minecraft worlds",
	"warning": "proxy spawn uses a 'file duplication hack'! Addon is WIP",
	"wiki_url": "https://github.com/TheDuckCow/MCprep.wiki.git",
	"author": "Patrick W. Crawford"
}

import bpy,os,mathutils,random,math



########
# add object instance not working, so workaround function:
def addGroupInstance(groupName,loc):
	scene = bpy.context.scene
	ob = bpy.data.objects.new(groupName, None)
	ob.dupli_type = 'GROUP'
	ob.dupli_group = bpy.data.groups.get(groupName)
	ob.location = loc
	scene.objects.link(ob)

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
# Operator, sets up the materials for better rendering
class materialChange(bpy.types.Operator):
	"""Preps selected minecraft materials"""
	bl_idname = "object.mc_mat_change"
	bl_label = "MCprep mats"
	bl_options = {'REGISTER', 'UNDO'}
	
	def execute(self, context):
		
		#get list of selected objects
		objList = context.selected_objects
		
		# defines lists for materials with special default settings.
		reflective = [ 'glass', 'glass_pane_side','ice']
		water = ['water']
		solid = ['sand','dirt','dirt_grass_side','dispenser_front','furnace_top','redstone_block',
				'gold_block','yourFace']
		emit= ['redstone_block','redstone_lamp_on','glowstone']
		
		
		for obj in objList:
			
			#DEBUG
			print('## {x}'.format(x=obj.name))
			
			#ignore non mesh selected objects
			if obj.type != 'MESH': continue
			
			
			###
			# Get materials
			# ultimately should put all materials into a LIST
			# then exit loop, and loop through MATERIALS to change
			
			#check that operation has not already been done to material:
			mat = obj.active_material
			try:
				newName = mat.name+'_tex' # add exception to skip? with warning?
				texList = mat.texture_slots.values()
			except:
				print('\tissue: no active material on object')
				continue
			
			
			### NOT generalized, ultimately will be looking for material in library blend
			try:
				if bpy.data.textures[texList[0].name].filter_type == 'BOX':
					continue #this skips this process, not added to matList, no doulbe mesh swapping
				bpy.data.textures[texList[0].name].name = newName
			except:
				print('\tissue: material '+mat.name+' has no texture slot. skipping...')
				continue
			
			######
			# Check for library material of same name, make true or false statement.
			libraryMaterial = False
			
			######
			# Setting the materials, library linked or pre-set defaults
			if libraryMaterial == True:
				print("library linked/appended material")
				print("not setup yet.")
				#include boolean linked variable for import to disable this
				#check if already linked (though nothing happens if it is anyways right?)
				# avoid having duplicates where possible...
			else:
				#mat = obj.material_slots[0] #assumes 1 material per object,
				#not ture if all joined together!
				bpy.data.materials[mat.name].use_transparent_shadows = True #all materials receive trans
				bpy.data.materials[mat.name].specular_intensity = 0
				for index in range(1,len(texList)):
					mat.texture_slots.clear(index) #clear out unnecessary texture slots?
						
				####
				#changing the actual changes for the default materials
				
				bpy.data.textures[newName].use_interpolation = False
				bpy.data.textures[newName].filter_type = 'BOX'
				bpy.data.textures[newName].filter_size = 0
				bpy.data.materials[mat.name].texture_slots[0].use_map_color_diffuse = True
				bpy.data.materials[mat.name].texture_slots[0].diffuse_color_factor = 1
				mat.use_textures[1] = False
		
				if not mat.name in solid: #ie alpha is on unless turned off, "safe programming"
					bpy.data.textures[newName].use_alpha = True
					bpy.data.materials[mat.name].texture_slots[0].use_map_alpha = True
					bpy.data.materials[mat.name].use_transparency = True
					bpy.data.materials[mat.name].alpha = 0
					bpy.data.materials[mat.name].texture_slots[0].alpha_factor = 1
					
				if mat.name in reflective:
					bpy.data.materials[mat.name].alpha=0.3
					bpy.data.materials[mat.name].raytrace_mirror.use = True
					bpy.data.materials[mat.name].raytrace_mirror.reflect_factor = 0.3
				
				if mat.name in emit:
					bpy.data.materials[mat.name].emit = 1
			

		return {'FINISHED'}



########
# Operator, funtion swaps meshes/groups from library file
class meshSwap(bpy.types.Operator):
	"""Swap minecraft import for custom 3D models"""
	bl_idname = "object.mc_meshswap"
	bl_label = "MCprep meshSwap"
	bl_options = {'REGISTER', 'UNDO'}
	
	
	def execute(self, context):
		
		## debug, restart check
		print('###################################')
		
		selList = context.selected_objects
		objList = []
		for obj in selList:
			#ignore non mesh selected objects
			if obj.type != 'MESH': continue
			objList.append(obj.name)
		
			
		# filename = os.path.join(os.path.dirname(bpy.data.filepath),
		# >> might be a fix for this.....
		
		# Getting library file. hacky as**.
		# We SHOULD BE GETTING PATH FROM THE UI panel.
		# then the DEFAULT is relative. or perhaps that's already defined
		# by blender (should funciton properly with the "make relative"
		# function from the file menu)
		libPathProp = context.scene.MCprep_library_path
		
		
		"""
		direc = None
		genPath = os.path.splitext(bpy.data.filepath)[0] #format: ['/some/path/blendfilename','blend']
		while genPath[-1] != '/':
			genPath = genPath[:-1]
		path1 = genPath[:-1]+ '/assets/' #same dir check
		genPath=genPath[:-1] #getting rid of that last '/'
		while genPath[-1] != '/':
			genPath = genPath[:-1]
		path2 = genPath[:-1] + '/assets/' #dir one higher check
		"""
		libPath = libPathProp
		if not(os.path.isdir(libPathProp)):
			#extract actual path from the relative one
			libPath = bpy.path.abspath(libPath)
			
			#the above jsut strips off the first / but won't
			# deal with correcting the relative ../../ ect paths.
		
		direc = libPath+'asset_meshSwap.blend/'
		print(direc)
		if not os.path.exists(direc[:-1]):
			print('No assets library!')
			#popup window
			#nolib_warning(bpy.types.Menu)
			return {'CANCELLED'}
		
		
		###
		# Now get a list of all objects in this blend file, and all groups
		# these lists below are temporary, but would be created automatically by the above
		meshSwapList = ['tall_grass','flower_red','flower_yellow','cobweb','redstone_lamp_on',
						'redstone_lamp_off','dead_shrub','sapling_oak','redstone_wire_off',
						'wheat']
		groupSwapList = ['redstone_torch_on','redstone_lamp_on','torch']
		TOSUPPORT = ['vines','bed...','ironbars...'] #does nothing
		
		
		#primary loop, for each OBJECT needing swapping //was material
		for swap in objList:
			
			# generalize name to do work on duplicated meshes,
			# need both stripped and original name!
			swapGen = nameGeneralize(swap)
			#print(">> ",swapGen,' ',swap)
			
			#special cases, for "extra" mesh pieces we don't want around afterwards
			#another to get rid of: special case TOPS of blocks..
			if swapGen == 'torch_flame': #make sure torch is one fo the imported groups!
				bpy.ops.object.select_all(action='DESELECT')
				bpy.data.objects[swap].select = True
				bpy.ops.object.delete()
			
			
			if not (swapGen in meshSwapList or swapGen in groupSwapList): continue		
			#SHORTCUT: just selecting mesh with same name accordinly.. ALSO only if in objList
			# shoudl also check different for
			
			#first go through and separate materials/faces of specific one into one mesh. I've got
			# that already, so moving on.
			#now you have object that has just that material. Known.
			toSwapObj = bpy.data.objects[swap] #the object that would be created above...
			objSwapList = bpy.data.meshes[swap] #the mesh that would be created above...
			
			#print('## mesh swapping: ',swap)
			
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
			
			
			bpy.ops.object.select_all(action='DESELECT')
			toSwapObj.select = True
			bpy.ops.object.delete() #Hey! The values of facebook are unchanged, so it's NOT linked..?
			
			
			### NOTE: NAMING ISSUES: IF there already was another mesh of the same name before importing,
			### the imported mesh REPLACES the old one. That's a problem. except in my special case.
			### perhaps just programatically change the name here
			
			# removing duplicates and checking orientation
			dupList = []	#where actual data is stored
			checkList = []	#where cross check data is stored
			for setNum in range(0,len(facebook)):
				
				# LOCAL coordinates!!!
				x = round(facebook[setNum][2][0]) #since center's are half ints.. 
				y = round(facebook[setNum][2][1]) #don't need (+0.5) -.5 structure
				z = round(facebook[setNum][2][2])
				
				if onEdge(facebook[setNum][2]): #check if face is on unit block boundary (local coord!)
					a = -facebook[setNum][0][0] * 0.5 #x normal
					b = -facebook[setNum][0][1] * 0.5 #y normal
					c = -facebook[setNum][0][2] * 0.5 #z normal
					x = round(facebook[setNum][2][0]+a) 
					y = round(facebook[setNum][2][1]+b)
					z = round(facebook[setNum][2][2]+c)
				
				#print(facebook[setNum][2][1]+0.5 - math.floor(facebook[setNum][2][1]+0.5))
				
				#check if height (that's the Y axis, since in local coords)
				if facebook[setNum][2][1]+0.5 - math.floor(facebook[setNum][2][1]+0.5) < 0.3:
					#continue if coord. is < 1/3 of block height
					continue
				
				# rotation value (second append value: 0 means nothing, rest 1-4.
				if not [[x,y,z],0] in dupList: #not generalized, should be also 0-> 1,2,3,4
					dupList.append([[x,y,z],0])
				
				####
				# HERE DO THE STUFF FOR  ROTATION, set =1,2,3 or 4 (0 un rotated)
				# set is dupList.append([1]), i.e. that second value.
				####
			
			
			#import: guaranteed to have same name as "appendObj" for the first instant afterwards
			grouped = False # used to check if to join or not
			if swapGen in groupSwapList:
				#special cases, make another list for this? number of variants can vary..
				if swapGen == "torch":
					bpy.ops.wm.link_append(directory=direc+'Group/', filename=swapGen+".1", link=True)
					bpy.ops.object.delete()
					bpy.ops.wm.link_append(directory=direc+'Group/', filename=swapGen+".2", link=True)
					bpy.ops.object.delete()
				bpy.ops.wm.link_append(directory=direc+'Group/', filename=swapGen, link=True) #make prop!
				bpy.ops.object.delete()
				grouped = True
			else:
				bpy.ops.wm.link_append(directory=direc+'Object/', filename=swapGen, link=False)

			
			# duplicating and moving
			dupedObj = []
			for set in dupList:
				loc = toSwapObj.matrix_world*mathutils.Vector(set[0]) #local to global
				
				if grouped:
					# definition for randimization, defined at top!
					randGroup = randomizeMeshSawp(swapGen,3)
					# The built in method fails, bpy.ops.object.group_instance_add(...)
					# ZZusing custom def instead
					#UPDATE: I reported the bug, and they fixed it nearly instantly =D
					# but it was recommended to do the below anyways.
					addGroupInstance(randGroup,loc)
					
				else:
					#sets location of current selection, imported object or group from above
					bpy.context.selected_objects[0].location = mathutils.Vector(loc) #hackish....
					dupedObj.append(bpy.context.selected_objects[0])
					bpy.ops.object.duplicate(linked=False, mode='TRANSLATION')
				
				#rotation/translation for on walls
				x,y,offset,rotValue,z = 0,0,0.28,0.436332,0.12
				if set[1] == 1:
					x = offset
					bpy.ops.transform.translate(value=(x, y, z))
					bpy.ops.transform.rotate(value=rotValue, axis=(0, 1, 0))
				if set[1] == 2:
					y = offset
					bpy.ops.transform.translate(value=(x, y, z))
					bpy.ops.transform.rotate(value=rotValue, axis=(1, 0, 0))
				if set[1] == 3:
					x = -offset
					bpy.ops.transform.translate(value=(x, y, z))
					bpy.ops.transform.rotate(value=-rotValue, axis=(0, 1, 0))
				if set[1] == 4:
					y = -offset
					bpy.ops.transform.translate(value=(x, y, z))
					bpy.ops.transform.rotate(value=-rotValue, axis=(1, 0, 0))
				
			if not grouped: bpy.ops.object.delete() # as there is one extra..
			
			
			#join meshes together
			if not grouped and (len(dupedObj) >0):
				#print(len(dupedObj))
				# ERROR HERE if don't do the len(dupedObj) thing.
				bpy.context.scene.objects.active = dupedObj[0]
				for d in dupedObj:
					d.select = True
				bpy.ops.object.join()
			
			#deselect? or try to reselect everything that was selected previoulsy

		
		return {'FINISHED'}


#######
# Class for updating the duplicated proxy spawn files
class proxyUpdate(bpy.types.Operator):
	"""Updates all proxy spawn files to be consistent"""
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
# pop-up declaring some button is WIP still =D
class nolib_warning(bpy.types.Menu):
	bl_label = "library_not_found_warning"
	bl_idname = "view3D.nolib_warning"

	# Set the menu operators and draw functions
	def draw(self, context):
		layout = self.layout

		row1 = layout.row()
		row1.label(text="Library file {x} not found")  

#######
# panel for these declared tools
class MCpanel(bpy.types.Panel):
	"""MCprep addon panel"""
	bl_label = "MCprep Panel"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'

	def draw(self, context):
		#MCprep = context.scene.object.mc_meshswap
		
		layout = self.layout

		split = layout.split()
		col = split.column(align=True)
		
		
		
		#URL path
		
		#image_settings = rd.image_settings
		#file_format = image_settings.file_format
		col.prop(context.scene,"MCprep_library_path",text="")
		# + naming convention
		# naming convention.. e.g. {x} for "asset" in any name/seciton of name
		
		
		
		
		#for setting MC materials and looking in library
		col.operator("object.mc_mat_change", text="Prep Materials", icon='MATERIAL')
		
		#below should actually just call a popup window
		col.operator("object.mc_meshswap", text="Mesh Swap", icon='IMPORT')
		split = layout.split()
		col = split.column(align=True)
		
		#spawn (makes UI pulldown)
		split2 = layout.split()
		col2 = split2.column(align=True)
		col2.label(text="Spawn proxy character")
		col2.menu("view3D.wip_warning", text="-select-")		 #meh, try to put on sme line as below
		col2.operator("mesh.primitive_cube_add", text="Proxy Spawn") #put on same line as above
		
		#update spawn files
		col2.operator("object.proxy_update", text="Update Spawn Proxies")
		#label + warning sign
		#col2.label(text="Update proxies after editing library!", icon='ERROR')
		#perhaps try to have it only show warning if detected inconsistent timestamps


#######

def register():
	bpy.utils.register_class(materialChange)
	bpy.utils.register_class(meshSwap)
	bpy.utils.register_class(proxyUpdate)
	
	bpy.utils.register_class(WIP)
	bpy.utils.register_class(MCpanel)
	bpy.utils.register_class(nolib_warning)
	
	#properties
	bpy.types.Scene.MCprep_library_path = bpy.props.StringProperty(
		name="",
		description="Location of asset library",
		default="//assets/",subtype="DIR_PATH",
		)


def unregister():
	bpy.utils.unregister_class(materialChange)
	bpy.utils.unregister_class(meshSwap)
	bpy.utils.unregister_class(proxyUpdate)
	
	bpy.utils.unregister_class(WIP)
	bpy.utils.unregister_class(MCpanel)
	bpy.utils.unregister_class(nolib_warning)
	
	#properties
	del bpy.types.Scene.MCprep_library_path


if __name__ == "__main__":
	register()



"""
try: import webbrowser
except: webbrowser = None

if webbrowser:
	webbrowser.open(self.__URL__)
else:
	raise Exception("Operator requires a full Python installation")

return ('FINISHED',)

"""