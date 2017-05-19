# ##### BEGIN MIT LICENSE BLOCK #####
#
# Copyright (c) 2016 Patrick W. Crawford
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####


# library imports
import bpy
from bpy_extras.io_utils import ImportHelper
import os
import math
import shutil
from mathutils import Vector

# addon imports
from . import conf
from . import util
from . import tracking



# -----------------------------------------------------------------------------
# support functions
# -----------------------------------------------------------------------------


# only used for UI drawing of enum menus, full list
def getRigList(context): #consider passing in rigpath

	# test the link path first!
	# rigpath = bpy.path.abspath(context.scene.mcrig_path) #addon_prefs.mcrig_path
	# blendFiles = []
	# pathlist = []
	# riglist = []

	if len(conf.rig_list)==0: # may redraw too many times, perhaps have flag
		return updateRigList(context)

	else:
		return conf.rig_list


# for UI list path callback
def update_rig_path(self, context):
	if conf.vv:print("Updating rig path")
	updateRigList(context)
	spawn_rigs_categories(self, context)

# Update the rig list and subcategory list
def updateRigList(context):
	# test the link path first!
	rigpath = bpy.path.abspath(context.scene.mcrig_path)
	blendFiles = []
	pathlist = []
	riglist = []
	conf.rig_list = []
	subriglist = []
	context.scene.mcprep_mob_list.clear()

	# iterate through all folders
	if len(os.listdir(rigpath)) < 1:
		#self.report({'ERROR'}, "Rig sub-folders not found")
		# should this really be an error? only if no local files too
		return# {'CANCELLED'}

	nocatpathlist = []
	for catgry in os.listdir(rigpath):

		it = os.path.join(rigpath,catgry) # make a full path
		#print("dir: ",it)
		if os.path.isdir(it) and it[0] != ".": # ignore hidden or structural files
			pathlist = []
			onlyfiles = [ f for f in os.listdir(it) if os.path.isfile(os.path.join(it,f)) ]
			#print("Through all files.., it:", it)
			for f in onlyfiles:
				# only get listing of .blend files
				if f.split('.')[-1] == 'blend':
					pathlist.append([os.path.join(it,f), os.path.join(catgry,f)])
					#print("found blend: ",os.path.join(it,f))
			for [rigPath,local] in pathlist:
				with bpy.data.libraries.load(rigPath) as (data_from, data_to):
					for name in data_from.groups:

						# special cases, skip some groups
						if name.lower() == "Rigidbodyworld".lower():
							continue 

						#if name in bpy.data.groups:
						#	if conf.v:print("Already grouped in this one. maybe should append the same way/rename?")
						#	riglist.append( ('//'+':/:'+name+':/:'+catgry,name,\
							#"Spawn a {x} rig (local)".format(x=name)) )
							## still append the group name, more of an fyi
						#else:
						#	riglist.append( (rigPath+':/:'+name+':/:'+catgry,name,"Spawn a {x} rig".format(x=name)) )
						description = "Spawn a {x} rig".format(x=name)
						riglist.append( (local+':/:'+name+':/:'+catgry,name.title(),description) )
						item = context.scene.mcprep_mob_list.add()
						item.label = description
						item.description = description
						item.name = name.title()
						# MAKE THE ABOVE not write the whole rigPath, slow an unnecessary;
		
		elif catgry.split('.')[-1] == 'blend': # not a folder.. a .blend
			nocatpathlist.append([os.path.join(rigpath,catgry), catgry])
	

	# Finally, update the list with non-categorized mobs
	for [rigPath,local] in nocatpathlist:
		with bpy.data.libraries.load(rigPath) as (data_from, data_to):
			for name in data_from.groups:
				# //\// as keyword for root directory
				riglist.append( (local+':/:'+name+':/:'+"//\//",name,"Spawn a {x} rig".format(x=name)) )

	# set output and update category listing

	# sort the list alphebtically by name, and if possible,
	# put the generic player mob first (or eventually, the "pinned" rig)
	temp, sorted_rigs = zip(*sorted(zip([rig[1].lower() for rig in riglist], riglist)))

	# put the generic play on top, special case
	# if "player" in temp:
	# 	ind = temp.index("player")
	# 	sorted_rigs = [sorted_rigs[ind]]+[sorted_rigs[:ind]]+[sorted_rigs[ind+1:]]

	#print("-------")
	#for a in sorted_rigs:print(a)
	#print("-------")
	conf.rig_list = sorted_rigs
	updateCategory(context)
	return conf.rig_list


def updateCategory(context):

	if len(conf.rig_list)==0:
		if conf.v:print("No rigs found, failed to update category")
		context.scene.mcprep_mob_list.clear()
		return

	category = context.scene.mcprep_props.spawn_rig_category
	filter = (category != "all")

	context.scene.mcprep_mob_list.clear()
	conf.rig_list_sub = []
	conf.active_mob_subind = -1 # temp assignment, for radio buttons

	for itm in conf.rig_list:
		sub = itm[0].split(":/:")
		if filter==True and sub[-1].lower() != category.lower():
			continue
		item = context.scene.mcprep_mob_list.add()
		if conf.v:print("Spawning:",sub, "#", itm)
		description = "Spawn a {x} rig".format(x=sub[1])
		item.label = description
		item.description = description
		item.name = sub[1].title()
		conf.rig_list_sub.append(itm)
		if itm[0] == conf.active_mob:
			conf.active_mob_subind = len(conf.rig_list_sub)-1


# -----------------------------------------------------------------------------
# class definitions
# -----------------------------------------------------------------------------



class MCPREP_reloadMobs(bpy.types.Operator):
	"""Force reload the mob spawner rigs, use after manually adding rigs to folders"""
	bl_idname = "mcprep.reload_mobs"
	bl_label = "Reload the rigs and cache"

	def execute(self,context):
		updateRigList(context)
		return {'FINISHED'}


class MCPREP_mobSpawner_direct(bpy.types.Operator):
	"""Instantly spawn this rig into scene, no menu"""
	bl_idname = "mcprep.mob_spawner_direct"
	bl_label = "Mob Spawner"
	bl_description = "Instantly spawn this rig into scene, no menu"
	bl_options = {'REGISTER', 'UNDO'}

	mcmob_index = bpy.props.IntProperty(
		name="Mob index",
		default=-1
		#min=0,
		#max=len(conf.rig_list_sub)-1
		)
	relocation = bpy.props.EnumProperty(
		items = [('None', 'Cursor', 'No relocation'),
				('Clear', 'Origin', 'Move the rig to the origin'),
				('Offset', 'Offset root', 'Offset the root bone to curse while moving the rest pose to the origin')],
		name = "Relocation"
		)
	toLink = bpy.props.BoolProperty(
		name = "Library Link",
		description = "Library link instead of append the group",
		default = False
		)
	clearPose = bpy.props.BoolProperty(
		name = "Clear Pose",
		description = "Clear the pose to rest position",
		default = True 
		)

	def execute(self, context):

		print(conf.rig_list_sub)
		# fix the index if needed
		# if self.mcmob_index>=len(conf.rig_list_sub):
		# 	self.mcmob_index = 0
		# 	print("Wraparound)")
		# elif self.mcmob_index<0:
		# 	self.mcmob_index = len(conf.rig_list_sub)-1
		# 	print("neg wraparound")

		if self.mcmob_index == -1:
			mob = ""
			self.report({'ERROR'},"Invalid mob index -1")
			return {'CANCELLED'}
		else:
			mob = conf.rig_list_sub[self.mcmob_index][0]

		bpy.ops.mcprep.mob_spawner('EXEC_DEFAULT',
				mcmob_type = mob,
				relocation = self.relocation,
				toLink = self.toLink,
				clearPose = self.clearPose)

		return {'FINISHED'}




class MCPREP_mobSpawner(bpy.types.Operator):
	"""Show menu and spawn built-in or custom rigs into a scene"""
	bl_idname = "mcprep.mob_spawner"
	bl_label = "Mob Spawner"
	bl_description = "Spawn built-in or custom rigs into a scene with menu"
	bl_options = {'REGISTER', 'UNDO'}

	# properties, will appear in redo-last menu
	def riglist_enum(self, context):
		return getRigList(context)

	mcmob_type = bpy.props.EnumProperty(items=riglist_enum, name="Mob Type") # needs to be defined after riglist_enum
	relocation = bpy.props.EnumProperty(
		items = [('None', 'Cursor', 'No relocation'),
				('Clear', 'Origin', 'Move the rig to the origin'),
				('Offset', 'Offset root', 'Offset the root bone to curse while moving the rest pose to the origin')],
		name = "Relocation"
		)
	toLink = bpy.props.BoolProperty(
		name = "Library Link",
		description = "Library link instead of append the group",
		default = False
		)
	clearPose = bpy.props.BoolProperty(
		name = "Clear Pose",
		description = "Clear the pose to rest position",
		default = True 
		)

	def draw(self, context):
		row = self.layout.row()
		row.prop(self,"mcmob_type")
		row = self.layout.row()
		row.prop(self,"relocation")

		row = self.layout.row(align=True)
		row.prop(self,"toLink")
		row.prop(self,"clearPose")
	

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def proxySpawn(self):
		if conf.v:print("Attempting to do proxySpawn")
		if conf.v:print("Mob to spawn: ",self.mcmob_type)

	def attemptScriptLoad(self,path):
		# search for script that matches name of the blend file
		# should also look into the blend if appropriate
		if path[-5:]=="blend":
			path = path[:-5]+"py"
			#bpy.ops.script.python_file_run(filepath=path)
			if not os.path.isfile(path):
				return # no script found
			if conf.v:print("Script found, loading and running it")
			bpy.ops.text.open(filepath=path,internal=True)
			text = bpy.data.texts[ path.split("/")[-1] ]
			text.use_module = True
			ctx = bpy.context.copy()
			ctx['edit_text'] = text
			bpy.ops.text.run_script(ctx)
			if conf.v:print("Ran the script")

	def setRootLocation(self,context):
		pass
		# should be the consolidated code for 
		# both linking and appending below, .. they branched right now.



	def execute(self, context):
		
		# only sends tracking if opted in
		tracking.trackUsage("mobSpawner",self.mcmob_type)

		try:
			[path,name,category] = self.mcmob_type.split(':/:')
			if conf.v:print("BEFORE path is",path)
			path = os.path.join(context.scene.mcrig_path,path)
			if conf.v:print("NOW path is",path)
		except:
			if conf.v:print("Error: No rigs found!")
			self.report({'ERROR'}, "No mobs found in folder!")
			return {'CANCELLED'}

		try:
			bpy.ops.object.mode_set(mode='OBJECT') # must be in object mode, this make similar behavior to other objs
		except:
			pass # can fail to this e.g. if no objects are selected

		if self.toLink:
			if path != '//':
				path = bpy.path.abspath(path)
				util.bAppendLink(os.path.join(path,'Group'),name, True)
				# proxy any and all armatures
				# here should do all that jazz with hacking by copying files, checking nth number
				#probably consists of checking currently linked libraries, checking if which
				#have already been linked into existing rigs
				try:
					# try also with capitor name? name.title()
					bpy.ops.object.proxy_make(object=name+'.arma')
					# this would be "good convention", but don't force it - let it also search through
					# and proxy every arma, regardless of name settings!

					if self.relocation == "Offset":
						# do the offset stuff, set active etc
						#bpy.ops.object.mode_set(mode='OBJECT')

						bpy.ops.transform.translate(value=(-gl[0],-gl[1],-gl[2]))
					
					act = context.active_object
					bpy.context.scene.objects.active = ob
					if conf.v:print("ACTIVE obj = {x}".format(x=ob.name))
					bpy.ops.object.mode_set(mode='POSE')
					if self.clearPose:
						#if conf.v:print("clear the stuff!")
						bpy.ops.pose.select_all(action='SELECT')
						bpy.ops.pose.rot_clear()
						bpy.ops.pose.scale_clear()
						bpy.ops.pose.loc_clear()
					if self.relocation == "Offset":
						tmp=0
						for nam in ["MAIN","root","base", "Root", "Base", "ROOT"]:
							if conf.v:print("Attempting offset root")
							if nam in ob.pose.bones and tmp==0:

								# this method doesn't work because, even though we are in POSE
								# mode, the context for the operator is defined at the start,
								# so acts as if in object mode.. which isn't helpful at all.
								# ob.pose.bones[nam].bone.select = True
								# bpy.ops.view3d.snap_selected_to_cursor(use_offset=True)
								# #ob.pose.bones[nam].bone.select = False
								# tmp=1 # to end loop early

								# these transforms.. are so weird. what. but it works..
								# but not for all, some rigs are different. need some kind
								# of transform to consider in, global vs local etc.
								# OLD way
								#ob.pose.bones[nam].location[0] = cl[0]
								#ob.pose.bones[nam].location[1] = cl[1]
								#ob.pose.bones[nam].location[2] = -cl[2]

								tmp=1

								# do global space method
								worldtrans = ob.matrix_world * ob.pose.bones[nam].matrix
								print(worldtrans)

								break
						if tmp==0:
							if conf.v:print("This addon works better when the root bone's name is 'MAIN'")
							elf.report({'INFO'}, "This addon works better when the root bone's name is 'MAIN'")

					# copied from below, should be the same

				except Exception as e:
					if conf.v:print("Spawner works better if the armature's name is {x}.arma".format(x=name))
					self.report({'INFO'}, "Works better if armature's name = {x}.arma".format(x=name))
					# self report?
					print("Spawning error: ",str(e))
					pass

			else:
				# .... need to do the hack with multiple mobs!!!
				if conf.v:print("THIS IS THE LOCAL FILE.") #not sure what that means here
		else:
			# append the rig, the whole group.. though honestly ideally not, and just append the right objs
			#idea: link in group, inevtiably need to make into this blend file but then get the remote's
			# all object names, then unlink/remove group (and object it creates) and directly append all those objects
			# OOORR do append the group, then remove the group but keep the individual objects
			# that way we know we don't append in too many objects (e.g. parents pulling in children/vice versa)

			# also issue of "undo/redo"... groups stay linked/ as groups even if this happens!	

			if path != '//': #ie not yet linked in.
				path = bpy.path.abspath(path)
				sel = bpy.context.selected_objects # capture state before, technically also copy
				bpy.ops.object.select_all(action='DESELECT')
				# consider taking pre-exisitng group names and giving them a temp name to name back at the end
				if conf.v:print(os.path.join(path,'Group'),name)
				util.bAppendLink(os.path.join(path,'Group'),name, False)
				
				try:
					g1 = context.selected_objects[0]  # THE FOLLOWING is a common fail-point.
					grp_added = g1.users_group[0] # to be safe, grab the group from one of the objects
				except:
					# this is more likely to fail but serves as a fallback
					if conf.v:print("Mob spawn: Had to go to fallback group name grab")
					grp_added = bpy.data.groups[name]
				
				gl = grp_added.dupli_offset # if rig not centered in original file, assume its group is
				cl = bpy.context.space_data.cursor_location

				#addedObjs = grp_added.objects
				addedObjs = context.selected_objects # why doesn't group added objects work?
				for a in addedObjs:
					a.select = True
					if a.hide:
						a.hide = False
						bpy.ops.group.objects_remove()
						a.hide = True
					else:
						bpy.ops.group.objects_remove()
				for a in grp_added.objects: # but this for selected objects doesn't work below.
					a.select = True
					if a not in addedObjs:
						addedObjs.append(a)
					if a.hide:
						a.hide = False
						bpy.ops.group.objects_remove()
						a.hide = True
					else:
						bpy.ops.group.objects_remove()

				grp_added.name = "reload-blend-to-remove-this-empty-group"
				bpy.ops.group.objects_remove_all() # just in case
				grp_added.user_clear() # next time blend file reloads, this group will be gone

				if self.clearPose or self.relocation=="Offset":
					#bpy.ops.object.select_all(action='DESELECT') # too soon?
					for ob in addedObjs:
						if ob.type == "ARMATURE" and util.nameGeneralize(ob.name)==name+'.arma':
							if conf.v:print("This is the one, ",ob.name)

							if self.relocation == "Offset":
								# do the offset stuff, set active etc
								#bpy.ops.object.mode_set(mode='OBJECT')
								bpy.ops.transform.translate(value=(-gl[0],-gl[1],-gl[2]))
							
							#bpy.ops.object.select_all(action='DESELECT')
							act = context.active_object
							bpy.context.scene.objects.active = ob
							if conf.v:print("ACTIVE obj = {x}".format(x=ob.name))
							try:
								bpy.ops.object.mode_set(mode='POSE')
							except Exception as e:
								self.report({'ERROR'},"Exception occured, see logs")
								print("Exception: ",str(e))
								print(bpy.context.scene.objects.active)
								print(ob)
								print("-- end error context printout --")
								continue
							if self.clearPose:
								if conf.v:print("clear the stuff!")

								#ob.animation_data_clear()
								if ob.animation_data:
									ob.animation_data.action = None
								
								# transition to clear out pose this way
								# for b in ob.pose.bones:


								# old way, with mode set
								bpy.ops.pose.select_all(action='SELECT')
								bpy.ops.pose.rot_clear()
								bpy.ops.pose.scale_clear()
								bpy.ops.pose.loc_clear()
								
								# preserve original selection? keep all selected
							if self.relocation == "Offset":
								tmp=0
								#bpy.ops.pose.select_all(action='DESELECT')
								for nam in ["MAIN","root","base"]:
									if conf.v:print("We are here right?")
									if nam in ob.pose.bones and tmp==0:

										# this method doesn't work because, even though we are in POSE
										# mode, the context for the operator is defined at the start,
										# so acts as if in object mode.. which isn't helpful at all.
										# ob.pose.bones[nam].bone.select = True
										# bpy.ops.view3d.snap_selected_to_cursor(use_offset=True)
										# #ob.pose.bones[nam].bone.select = False
										# tmp=1 # to end loop early


										# these transforms.. are so weird. what. but it works..
										# but not for all, some rigs are different. need some kind
										# of transform to consider in, global vs local etc.
										# OLD ways
										# ob.pose.bones[nam].location[0] = cl[0]
										# ob.pose.bones[nam].location[1] = cl[1]
										# ob.pose.bones[nam].location[2] = -cl[2]
										tmp=1

										# do global space method
										ob.pose.bones[nam].location = \
												ob.matrix_world.inverted() * \
												ob.pose.bones[nam].bone.matrix_local.inverted() * context.scene.cursor_location
										print("Updated location: ")
										print(ob.pose.bones[nam].location)

								if tmp==0:
									if conf.v:print("This addon works better when the root bone's name is 'MAIN'")
									self.report({'INFO'}, "This addon works better when the root bone's name is 'MAIN'")

							bpy.ops.object.mode_set(mode='OBJECT')
							# bpy.context.scene.objects.active = act  # # no, make the armatures active!
							break #end the for loop, only one thing to offset!
						elif ob.type == "ARMATURE" and self.clearPose:
							if ob.animation_data:
								ob.animation_data.action = None
							# just general armature, still clear pose if appropriate
							#bpy.ops.object.select_all(action='DESELECT')
							act = context.active_object
							bpy.context.scene.objects.active = ob
							if conf.v:print("ACTIVE obj = {x}".format(x=ob.name))
							
							try:
								bpy.ops.object.mode_set(mode='POSE')

								if conf.v:print("clear the stuff!")
								bpy.ops.pose.select_all(action='SELECT')
								bpy.ops.pose.rot_clear()
								bpy.ops.pose.scale_clear()
								bpy.ops.pose.loc_clear()
								bpy.ops.object.mode_set(mode='OBJECT')
								#bpy.context.scene.objects.active = act # no, make the armatures active!
							except Exception as e:
								print("ERROR: #spawner_575, encountered issue entering object mode but should have been fine")
								self.report({'ERROR'},"Exception occured, see logs")
								print("Exception: ",str(e))
								print(bpy.context.scene.objects.active)
								print(ob)
								print("-- end error context printout --")
								continue
				else:
					# just make sure the last object selected is an armature, for each pose mode
					for ob in addedObjs:
						if ob.type == "ARMATURE":
							bpy.context.scene.objects.active = ob
				# now do the extra options, e.g. the offsets
				if self.relocation == "Clear":
					bpy.ops.transform.translate(value=(-gl[0],-gl[1],-gl[2]))
				elif self.relocation=="None":
					bpy.ops.transform.translate(value=(cl[0]-gl[0],cl[1]-gl[1],cl[2]-gl[2]))

				# add the original selection back
				for ob in sel:
					ob.select = True

			else:
				# here this means the group HAS already been appended.. recopy thsoe elements, or try re-appending?
				# (yes, should try re-appending. may need to rename group)
				self.report({'ERROR'}, "Group name already exists in local file")
				if conf.v:print("Group already appended/is here") #... so hack 'at it and rename it, append, and rename it back?

		# if there is a script with this rig, attempt to run it
		self.attemptScriptLoad(path)
		if context.scene.render.engine == 'CYCLES':
			if conf.internal_change == False:
				conf.internal_change = True
				bpy.ops.mcprep.mat_change(skipUsage=True) # if cycles
				conf.internal_change = False
			else:
				bpy.ops.mcprep.mat_change(skipUsage=True) # if cycles

		return {'FINISHED'}


class MCPREP_installMob(bpy.types.Operator, ImportHelper):
	"""Install custom rig popup for the mob spawner, all groups in selected blend file will become individually spawnable"""
	bl_idname = "mcprep.mob_install_menu"
	bl_label = "Install new mob"

	filename_ext = ".blend"
	filter_glob = bpy.props.StringProperty(
			default="*.blend",
			options={'HIDDEN'},
			)
	fileselectparams = "use_filter_blender"
	# property for which folder it goes in
	# blaaaaaa default to custom I guess
	def getCategories(self, context):
		#addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		ret = []
		path = bpy.path.abspath(context.scene.mcrig_path)
		onlyfiles = [ f for f in os.listdir(path) if os.path.isdir(os.path.join(path,f)) ]
		ret.append(  ("all","All mobs","All mobs"))
		for a in onlyfiles:
			if a==".DS_Store":continue
			ret.append(  (a, a.title(), "{x} mob".format(x=a.title()))  )
		ret.append( ("no_category", "No Category", "Uncategorized mob") ) # last entry
		return ret


	mob_category = bpy.props.EnumProperty(
		items = getCategories,
		name = "Mob Category")
	#[('custom', 'Custom', 'Custom mob'),('passive', 'Passive', 'Passive mob')]

	def installBlend(self, context, filepath):
		#addon_prefs = bpy.context.user_preferences.addons[__package__].preferences

		#check blend input file exists
		drpath = context.scene.mcrig_path #addon_prefs.mcrig_path
		newrig = bpy.path.abspath(filepath)
		if not os.path.isfile(newrig):
			if conf.v:print("Error: Rig blend file not found!")
			self.report({'ERROR'}, "Rig blend file not found!")
			return {'CANCELLED'}

		# now check the rigs folder indeed exists
		drpath = bpy.path.abspath(drpath)
		if not os.path.isdir(drpath):
			if conf.v:print("Error: Rig directory is not valid!")
			self.report({'ERROR'}, "Rig directory is not valid!")
			return {'CANCELLED'}
		
		# check the file with a quick look for any groups, any error return failed
		with bpy.data.libraries.load(newrig) as (data_from, data_to):
			if len(data_from.groups) < 1:
				if conf.v:print("Error: no groups found in blend file!")
				self.report({'ERROR'}, "No groups found in blend file!")
				return {'CANCELLED'}

		# copy this file to the rig folder
		filename = (newrig).split('/')[-1]
		# path:rig folder / category / blend file
		try:
			#shutil.copyfile(newrig, os.path.join(os.path.join(drpath,self.mob_category) , filename))
			# alt method, perhaps works for more people? at least one person couldn't prev. version, I assume
			# the above line was the failing point.
			if self.mob_category != "no_category":
				shutil.copy2(newrig, os.path.join(os.path.join(drpath,self.mob_category) , filename))
				if os.path.isfile(newrig[:-5]+"py"):
					# if there is a script, install that too
					shutil.copy2(newrig[:-5]+"py", os.path.join(os.path.join(drpath,self.mob_category) , filename[:-5]+"py"))
			else:
				shutil.copy2(newrig, os.path.join(drpath , filename)) # no category, root of directory
				if os.path.isfile(newrig[:-5]+"py"):
					shutil.copy2(newrig[:-5]+"py", os.path.join(drpath , filename[:-5]+"py")) # no category, root of directory
					
		except:
			# can fail if permission denied, i.e. an IOError error
			self.report({'ERROR'}, "Failed to copy, manually install my copying rig to folder: {x}".\
					format(x=os.path.join(drpath,self.mob_category)))
			return {'CANCELLED'}

		# reload the cache
		updateRigList(context)
		self.report({'INFO'}, "Mob-file Installed")

		return {'FINISHED'}

	def execute(self, context):
		# addon_prefs.mcmob_install_new_path = "//" # clear the path after install, to show it's not like a saved thing.
		# self.filepath = "//"
		return self.installBlend(context,self.filepath)
		#return {'FINISHED'} returned in the sub functions


class MCPREP_openRigFolder(bpy.types.Operator):
	"""Open the rig folder for mob spawning"""
	bl_idname = "mcprep.openrigpath"
	bl_label = "Open rig folder"

	def execute(self,context):
		#addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		import subprocess
		try:
			# windows... untested
			subprocess.Popen('explorer "{x}"'.format(x=bpy.path.abspath(context.scene.mcrig_path)))
		except:
			try:
				# mac... works on Yosemite minimally
				subprocess.call(["open", bpy.path.abspath(context.scene.mcrig_path)])
			except:
				# linux
				try:
					subprocess.call(["xdg-open", bpy.path.abspath(context.scene.mcrig_path)])
				except:
					self.report({'ERROR'}, "Didn't open folder, navigate to it manually: {x}".format(x=context.scene.mcrig_path))
					return {'CANCELLED'}
		return {'FINISHED'}



class MCPREP_spawnPathReset(bpy.types.Operator):
	"""Reset the spawn path to the default specified in the addon preferences panel"""
	bl_idname = "mcprep.spawnpathreset"
	bl_label = "Reset spawn path"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self,context):
		
		addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
		context.scene.mcrig_path = addon_prefs.mcrig_path
		updateRigList(context)
		return {'FINISHED'}



class MCPREP_uninstallMob(bpy.types.Operator):
	bl_idname = "mcprep.mob_uninstall"
	bl_label = "Uninstall selected mob by deleting source blend file"

	path = ""
	listing = []

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def preDraw(self, context):
		mob = conf.rig_list_sub[context.scene.mcprep_mob_list_index]

		try:
			print(mob)
			[path,name,category] = mob[0]
			path = os.path.join(context.scene.mcrig_path,path)
		except Exception as e:
			self.report({'ERROR'}, "Could not resolve file to delete")
			print("Error: {}".format(e))
			return {'CANCELLED'}

		# see how many groups use this blend file
		count = 0
		listing = ""
		for grp in conf.riglist:
			if grp[0][0] == path:
				listing.append(grp[0][1])
				count+=1


	def draw(self, context):
		row = self.layout.row()
		row.label("Multiple mobs found in target blend file:")
		row = self.layout.row()

		# draw 3-column list of mobs to be deleted
		col1 = row.column()
		col2 = row.column()
		col3 = row.column()
		count = 0
		for grp in self.listing:
			count+=1
			if count%3==0:
				col1.label(grp)
			elif count%3==1:
				col2.label(grp)
			else:
				col3.label(grp)
		row = self.layout.row()
		row.label("Press okay to remove all, or press esc to cancel")


	def execute(self,context):
		
		mob = conf.rig_list_sub[context.scene.mcprep_mob_list_index]
		try:
			[path,name,category] = mob[0]
			path = os.path.join(context.scene.mcrig_path,path)
		except:
			self.report({'ERROR'}, "Could not resolve file to delete")
			return {'CANCELLED'}

		# see how many groups use this blend file
		count = 0
		listing = ""
		for grp in conf.riglist:
			if grp[0][0] == path:
				#listing.append(grp[0][1])
				listing += grp[0][1] + ":/:"
				count+=1

		if count>1:
			#warning menu to indicate the fact there is more than one group
			#self.report({'ERROR'}, "Would delete more than one group")
			# listing , pass this into next function which acknwoledges all removing 
			#liststr

			bpy.ops.mcprep.mob_uninstall_all_in_file(path=path, listing=liststr)

			pass
		else:
			if os.path.isfile(path) == False:
				if conf.v:print("Error: Source file not found, didn't delete")
				self.report({'ERROR'}, "Source file not found, didn't delete")
			else:
				os.remove(path)

		return {'FINISHED'}



class MCPREP_uninstallMobs(bpy.types.Operator):
	"""If uninstalling a mob file contianing other mobs, delete anyways"""
	bl_idname = "mcprep.mob_uninstall_all_in_file"
	bl_label = "Uninstall all mobs in source blend file"

	path = bpy.props.StringProperty(default="")
	listing = bpy.props.StringProperty(default="")

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def draw(self, context):
		row = self.layout.row()
		row.label("Multiple mobs found in target blend file:")
		row = self.layout.row()

		# draw 3-column list of mobs to be deleted
		col1 = row.column()
		col2 = row.column()
		col3 = row.column()
		count = 0
		for grp in self.listing.split(":/:"):
			count+=1
			if count%3==0:
				col1.label(grp)
			elif count%3==1:
				col2.label(grp)
			else:
				col3.label(grp)

		row = self.layout.row()
		row.label("Press okay to remove all, or press esc to cancel")

	def execute(self,context):

		if os.path.isfile(self.path) == False:
			if conf.v:print("Error: Source file not found, didn't delete")
			self.report({'ERROR'}, "Source file not found, didn't delete")
		else:
			os.remove(self.path)

		return {'FINISHED'}



class MCPREP_spawnerActiveMob(bpy.types.Operator):
	"""Set the active mob radio head, separate from selection"""
	bl_idname = "mcprep.spawner_set_active_mob"
	bl_label = "Press to set active for quick spawning in skin swapper panel"

	index = bpy.props.IntProperty(
		name = "Active mob index",
		description = "Set the active mob index for other uses",
		default = -1
		)

	def execute(self, context):

		conf.active_mob_subind = self.index
		if self.index == -1:
			conf.active_mob = ""
		else:
			conf.active_mob = conf.rig_list_sub[self.index][0]

		return {'FINISHED'}



# -----------------------------------------------------------------------------
#	Mob category related
# -----------------------------------------------------------------------------


def spawn_rigs_categories(self, context):
	items = []
	items.append(("all","All mobs","Show all mobs loaded"))

	categories = conf.rig_categories
	if len(conf.rig_categories)==0:
		it = context.scene.mcrig_path
		categories = [ f for f in os.listdir(it) if os.path.isdir(os.path.join(it,f)) ]
		conf.rig_categories = categories
	
	for item in categories: #
		items.append((item, item+" mobs", "Show all mobs in the '"+item+"' category"))
	
	items.append(("no_category","Uncategorized","Show all uncategorized mobs"))
	return items


def spawn_rigs_category_load(self, context):
	# what happens when you load a NEW category of mobs
	print("New category selected!")
	# all handled in this loading module anyways
	updateCategory(context)

	return


# -----------------------------------------------------------------------------
#	UI list related
# -----------------------------------------------------------------------------


# for asset listing UIList drawing
class MCPREP_mob_UIList(bpy.types.UIList):
	def draw_item(self, context, layout, data, set, icon, active_data, active_propname, index):

		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			col = layout.column()
			col.prop(set, "name", text="", emboss=False)
			#layout.label(text='', icon='TIME')

			if conf.active_mob_subind == index:
				ic = "RADIOBUT_ON"
				layout.label("Skin swap")
			else:
				ic = "RADIOBUT_OFF"

			col = layout.column()
			row = col.row()
			row.scale_x = 0.25
			row.operator('mcprep.spawner_set_active_mob', emboss=False, text='',
                        icon=ic).index = index
			row.operator('mcprep.mob_spawner_direct',emboss=False, text='',
						icon='FORWARD').mcmob_index = index

		elif self.layout_type in {'GRID'}:
			layout.alignment = 'CENTER'
			layout.label("", icon='QUESTION')


# for asset listing
class ListColl(bpy.types.PropertyGroup):
	label = bpy.props.StringProperty()
	description = bpy.props.StringProperty()


# -----------------------------------------------------------------------------
#	Above for class functions/operators
#	Below for UI/register
# -----------------------------------------------------------------------------


def register():
	bpy.types.Scene.mcprep_mob_list = \
			bpy.props.CollectionProperty(type=ListColl)
	bpy.types.Scene.mcprep_mob_list_index = bpy.props.IntProperty(default=0)


def unregister():
	del bpy.types.Scene.mcprep_mob_list
	del bpy.types.Scene.mcprep_mob_list_index

