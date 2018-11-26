# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####


# library imports
import bpy
from bpy_extras.io_utils import ImportHelper
import os
import math
import shutil
from mathutils import Vector

# addon imports
from .. import conf
from .. import util
from .. import tracking


# -----------------------------------------------------------------------------
# support functions
# -----------------------------------------------------------------------------


def getRigList(context): #consider passing in rigpath
	"""Only used for UI drawing of enum menus, full list."""
	# test the link path first!
	# rigpath = bpy.path.abspath(context.scene.mcprep_mob_path) #addon_prefs.mcprep_mob_path
	# blendFiles = []
	# pathlist = []
	# riglist = []

	if len(conf.rig_list)==0: # may redraw too many times, perhaps have flag
		return updateRigList(context)
	else:
		return conf.rig_list


def update_rig_path(self, context):
	"""List for UI items callback of property spawn_rig_category."""
	if conf.vv:print("Updating rig path")
	updateRigList(context)
	spawn_rigs_categories(self, context)


def updateRigList(context):
	"""Update the rig list and subcategory list."""
	rigpath = bpy.path.abspath(context.scene.mcprep_mob_path)
	blendFiles = []
	pathlist = []
	riglist = []
	conf.rig_list = []
	subriglist = []
	context.scene.mcprep_props.mob_list.clear()

	# iterate through all folders
	if len(os.listdir(rigpath)) < 1:
		#self.report({'ERROR'}, "Rig sub-folders not found")
		# should this really be an error? only if no local files too
		return# {'CANCELLED'}

	nocatpathlist = []
	for catgry in os.listdir(rigpath):
		it = os.path.join(rigpath,catgry) # make a full path
		if os.path.isdir(it) and it[0] != ".": # ignore hidden or structural files
			pathlist = []
			onlyfiles = [ f for f in os.listdir(it) if os.path.isfile(os.path.join(it,f)) ]
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
						description = "Spawn one {x} rig".format(x=name)
						riglist.append( (local+':/:'+name+':/:'+catgry,name.title(),description) )
						item = context.scene.mcprep_props.mob_list.add()
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
	temp, sorted_rigs = zip(*sorted(zip(
		[rig[1].lower() for rig in riglist],
		riglist)))

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
		context.scene.mcprep_props.mob_list.clear()
		return

	category = context.scene.mcprep_props.spawn_rig_category
	filter = (category != "all")

	context.scene.mcprep_props.mob_list.clear()
	conf.rig_list_sub = []
	conf.active_mob_subind = -1 # temp assignment, for radio buttons

	for itm in conf.rig_list:
		sub = itm[0].split(":/:")
		if filter and sub[-1].lower() != category.lower():
			continue
		item = context.scene.mcprep_props.mob_list.add()
		description = "Spawn a {x} rig".format(x=sub[1])
		item.label = description
		item.description = description
		item.name = sub[1].title()
		conf.rig_list_sub.append(itm)
		if itm[0] == conf.active_mob:
			conf.active_mob_subind = len(conf.rig_list_sub)-1

	if context.scene.mcprep_props.mob_list_index > len(conf.rig_list_sub):
		context.scene.mcprep_props.mob_list_index = len(conf.rig_list_sub)-1


# -----------------------------------------------------------------------------
# class definitions
# -----------------------------------------------------------------------------


class McprepReloadMobs(bpy.types.Operator):
	"""Force reload the mob spawner rigs, use after manually adding rigs to folders"""
	bl_idname = "mcprep.reload_mobs"
	bl_label = "Reload the rigs and cache"

	@tracking.report_error
	def execute(self, context):
		updateRigList(context)
		return {'FINISHED'}


class McprepMobSpawnerDirect(bpy.types.Operator):
	"""Instantly spawn this rig into scene, no menu"""
	bl_idname = "mcprep.mob_spawner_direct"
	bl_label = "Mob Spawner"
	bl_description = "Instantly spawn this rig into scene, no menu"
	bl_options = {'REGISTER', 'UNDO'}

	mcmob_index = bpy.props.IntProperty(
		name="Mob index",
		default=-1,
		min=-1,
		#max=len(conf.rig_list_sub)-1
		options={'HIDDEN'}
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
		default = False
		)

	@tracking.report_error
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


class McprepMobSpawner(bpy.types.Operator):
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
	auto_prep = bpy.props.BoolProperty(
		name = "Prep materials (will reset Cycles nodes)",
		description = "Prep materials of the added rig, will replace cycles node groups with default",
		default = True
		)

	def draw(self, context):
		# row = self.layout.row()
		# row.prop(self,"mcmob_type")
		row = self.layout.row()
		row.prop(self,"relocation")

		row = self.layout.row(align=True)
		row.prop(self,"toLink")
		row.prop(self,"clearPose")
		row = self.layout.row(align=True)
		row.prop(self,"auto_prep")

	# def invoke(self, context, event):
	# 	return context.window_manager.invoke_props_dialog(self)

	def proxySpawn(self):
		if conf.v:
			print("Attempting to do proxySpawn")
			print("Mob to spawn: ", self.mcmob_type)

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

	track_function = "mobSpawner"
	track_param = None
	@tracking.report_error
	def execute(self, context):
		try:
			[path, name, _] = self.mcmob_type.split(':/:')
			path = os.path.join(context.scene.mcprep_mob_path,path)
			if conf.v:print("Path is now ",path)
		except:
			if conf.v:print("Error: No rigs found!")
			self.report({'ERROR'}, "No mobs found in folder!")
			return {'CANCELLED'}

		try:
			# must be in object mode, this make similar behavior to other objs
			bpy.ops.object.mode_set(mode='OBJECT')
		except:
			pass # can fail to this e.g. if no objects are selected

		if self.toLink:
			if path != '//':
				# not sure what that means here
				if conf.v:print("This is the local file. Cancelling...")
				return {'CANCELLED'}
			res = self.load_linked(context, path, name)
		else:
			# append the rig, the whole group.. though honestly ideally not, and just append the right objs
			#idea: link in group, inevtiably need to make into this blend file but then get the remote's
			# all object names, then unlink/remove group (and object it creates) and directly append all those objects
			# OOORR do append the group, then remove the group but keep the individual objects
			# that way we know we don't append in too many objects (e.g. parents pulling in children/vice versa)
			res = self.load_append(context, path, name)
			# also issue of "undo/redo"... groups stay linked/ as groups even if this happens!

		# if there is a script with this rig, attempt to run it
		self.attemptScriptLoad(path)

		if self.auto_prep:
			if not conf.internal_change:
				conf.internal_change = True
				bpy.ops.mcprep.prep_materials(skipUsage=True)
				conf.internal_change = False
			else:
				bpy.ops.mcprep.prep_materials(skipUsage=True)

		self.track_param = self.mcmob_type.split(":/:")[1]
		return {'FINISHED'}

	def load_linked(self, context, path, name):
		"""Process for loading mob via linked library"""

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

	def load_append(self, context, path, name):
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
			for ob in grp_added.objects:
			    grp_added.objects.unlink(ob)
			grp_added.user_clear()
			try:
				bpy.data.groups.remove(grp_added)
			except:
				pass

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



class McprepInstallMob(bpy.types.Operator, ImportHelper):
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
		ret = []
		path = bpy.path.abspath(context.scene.mcprep_mob_path)
		onlyfiles = [ f for f in os.listdir(path) if os.path.isdir(os.path.join(path,f)) ]
		ret.append(  ("all","No Category", "Uncategorized mob"))
		for a in onlyfiles:
			if a==".DS_Store":continue
			ret.append(  (a, a.title(), "{x} mob".format(x=a.title()))  )
		# ret.append( ("no_category", "No Category", "Uncategorized mob") ) # last entry
		return ret


	mob_category = bpy.props.EnumProperty(
		items = getCategories,
		name = "Mob Category")

	def installBlend(self, context, filepath):

		#check blend input file exists
		drpath = context.scene.mcprep_mob_path #addon_prefs.mcprep_mob_path
		newrig = bpy.path.abspath(filepath)
		category = self.mob_category

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
			if self.mob_category != "no_category" and self.mob_category != "all":
				shutil.copy2(newrig,
					os.path.join(drpath, self.mob_category, filename))
				if os.path.isfile(newrig[:-5]+"py"):
					# if there is a script, install that too
					shutil.copy2(newrig[:-5]+"py",
						os.path.join(drpath, self.mob_category, filename[:-5]+"py"))
			else:
				# no category, root of directory
				shutil.copy2(newrig, os.path.join(drpath , filename))
				if os.path.isfile(newrig[:-5]+"py"):
					# if there is a script, install that too
					shutil.copy2(newrig[:-5]+"py",
					os.path.join(drpath, filename[:-5]+"py"))

		except IOError as err:
			print(err)
			# can fail if permission denied, i.e. an IOError error
			self.report({'ERROR'}, "Failed to copy, manually install my copying rig to folder: {x}".\
					format(x=os.path.join(drpath,self.mob_category)))
			return {'CANCELLED'}

		# reload the cache
		updateRigList(context)
		self.report({'INFO'}, "Mob-file Installed")

		return {'FINISHED'}

	@tracking.report_error
	def execute(self, context):
		# addon_prefs.mcmob_install_new_path = "//" # clear the path after install, to show it's not like a saved thing.
		# self.filepath = "//"
		return self.installBlend(context,self.filepath)
		#return {'FINISHED'} returned in the sub functions


class McprepUninstallMob(bpy.types.Operator):
	"""Uninstall selected mob by deleting source blend file"""
	bl_idname = "mcprep.mob_uninstall"
	bl_label = "Uninstall mob"

	path = ""
	listing = []

	def invoke(self, context, event):
		self.preDraw(context)
		return context.window_manager.invoke_props_dialog(self, width=400*util.ui_scale())

	def preDraw(self, context):
		mob = conf.rig_list_sub[context.scene.mcprep_props.mob_list_index]
		self.path = ""

		try:
			self.path = mob[0].split(":/:")[0]
		except Exception as e:
			self.report({'ERROR'}, "Could not resolve file to delete")
			print("Error: {}".format(e))
			return {'CANCELLED'}

		# see how many groups use this blend file
		count = 0
		self.listing = []
		for grp in conf.rig_list:
			if grp[0].split(":/:")[0] == self.path:
				self.listing.append(grp[0].split(":/:")[1])
				count+=1

	def draw(self, context):

		row = self.layout.row()
		row.scale_y=0.5
		mob = conf.rig_list_sub[context.scene.mcprep_props.mob_list_index]
		path = mob[0].split(":/:")[0]
		path = os.path.join(context.scene.mcprep_mob_path,path)
		if len(self.listing)>1:
			row.label("Multiple mobs found in target blend file:")
			row = self.layout.row()
			row.scale_y=0.5

			# draw 3-column list of mobs to be deleted
			col1 = row.column()
			col1.scale_y=0.5
			col2 = row.column()
			col2.scale_y=0.5
			col3 = row.column()
			col3.scale_y=0.5
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
			row.label("Press okay to delete these mobs and file:")
		else:
			col = row.column()
			col.scale_y = 0.7
			col.label("Press okay to delete mob and file:")
		row = self.layout.row()
		row.label(path)


	@tracking.report_error
	def execute(self,context):

		mob = conf.rig_list_sub[context.scene.mcprep_props.mob_list_index]
		try:
			path = mob[0].split(":/:")[0]
			path = os.path.join(context.scene.mcprep_mob_path,path)
		except Exception as e:
			self.report({'ERROR'}, "Could not resolve file to delete")
			print("Error trying to remove mob file: "+str(e))
			return {'CANCELLED'}

		if os.path.isfile(path) == False:
			if conf.v:
				print("Error: Source filepath not found, didn't delete")
				print("path: "+path)
			self.report({'ERROR'}, "Source filepath not found, didn't delete")
			return {'CANCELLED'}
		else:
			try:
				os.remove(path)
			except:
				if conf.v:print("Error: could not delete file")
				self.report({'ERROR'}, "Could not delete file")
				return {'CANCELLED'}
		self.report({'INFO'},"Removed: "+str(path))
		if conf.v:print("Removed file: "+str(path))
		bpy.ops.mcprep.reload_mobs()
		return {'FINISHED'}


# -----------------------------------------------------------------------------
#	Mob category related
# -----------------------------------------------------------------------------


def spawn_rigs_categories(self, context):
	items = []
	items.append(("all","All mobs","Show all mobs loaded"))

	categories = conf.rig_categories
	if len(conf.rig_categories)==0:
		it = context.scene.mcprep_mob_path
		categories = [ f for f in os.listdir(it) if os.path.isdir(os.path.join(it,f)) ]
		conf.rig_categories = categories

	for item in categories: #
		items.append((item, item+" mobs", "Show all mobs in the '"+item+"' category"))

	items.append(("no_category","Uncategorized","Show all uncategorized mobs"))
	return items


def spawn_rigs_category_load(self, context):
	"""Update function for UI property spawn rig category"""
	updateCategory(context)
	return


# -----------------------------------------------------------------------------
#	Registration
# -----------------------------------------------------------------------------


def register():
	pass

def unregister():
	pass
