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

"""Blender UI integrations for the addon updater.

Implements draw calls, popups, and operators that use the addon_updater.
"""

import os
import traceback

import bpy
from bpy.app.handlers import persistent

from . import tracking

# Safely import the updater.
# Prevents popups for users with invalid python installs e.g. missing libraries
# and will replace with a fake class instead if it fails (so UI draws work).
try:
	from .addon_updater import Updater as updater
except Exception as e:
	print("ERROR INITIALIZING UPDATER")
	print(str(e))
	traceback.print_exc()

	class SingletonUpdaterNone(object):
		"""Fake, bare minimum fields and functions for the updater object."""

		def __init__(self):
			self.invalid_updater = True  # Used to distinguish bad install.

			self.addon = None
			self.verbose = False
			self.use_print_traces = True
			self.error = None
			self.error_msg = None
			self.async_checking = None

		def clear_state(self):
			self.addon = None
			self.verbose = False
			self.invalid_updater = True
			self.error = None
			self.error_msg = None
			self.async_checking = None

		def run_update(self, force, callback, clean):
			pass

		def check_for_update(self, now):
			pass

	updater = SingletonUpdaterNone()
	updater.error = "Error initializing updater module"
	updater.error_msg = str(e)

# Must declare this before classes are loaded, otherwise the bl_idname's will
# not match and have errors. Must be all lowercase and no spaces! Should also
# be unique among any other addons that could exist (using this updater code),
# to avoid clashes in operator registration.
updater.addon = "mcprep"


# -----------------------------------------------------------------------------
# Blender version utils
# -----------------------------------------------------------------------------
def make_annotations(cls):
	"""Add annotation attribute to fields to avoid Blender 2.8+ warnings.

	Deprecated operator as MCprep 3.5 moves to support 2.8+ only and using
	native python annotations.
	"""
	if not hasattr(bpy.app, "version") or bpy.app.version < (2, 80):
		return cls
	if bpy.app.version < (2, 93, 0):
		bl_props = {k: v for k, v in cls.__dict__.items()
					if isinstance(v, tuple)}
	else:
		bl_props = {k: v for k, v in cls.__dict__.items()
					if isinstance(v, bpy.props._PropertyDeferred)}
	if bl_props:
		if '__annotations__' not in cls.__dict__:
			setattr(cls, '__annotations__', {})
		annotations = cls.__dict__['__annotations__']
		for k, v in bl_props.items():
			annotations[k] = v
			delattr(cls, k)
	return cls


def layout_split(layout, factor=0.0, align=False):
	"""Intermediate method for pre and post blender 2.8 split UI function"""
	if not hasattr(bpy.app, "version") or bpy.app.version < (2, 80):
		return layout.split(percentage=factor, align=align)
	return layout.split(factor=factor, align=align)


def get_user_preferences(context=None):
	"""Intermediate method for pre and post blender 2.8 grabbing preferences"""
	if not context:
		context = bpy.context
	prefs = None
	if hasattr(context, "user_preferences"):
		prefs = context.user_preferences.addons.get(__package__, None)
	elif hasattr(context, "preferences"):
		prefs = context.preferences.addons.get(__package__, None)
	if prefs:
		return prefs.preferences
	# To make the addon stable and non-exception prone, return None
	# raise Exception("Could not fetch user preferences")
	return None


# -----------------------------------------------------------------------------
# Updater operators
# -----------------------------------------------------------------------------


# Simple popup to prompt use to check for update & offer install if available.
class AddonUpdaterInstallPopup(bpy.types.Operator):
	"""Check and install update if available"""
	bl_label = "Update {x} addon".format(x=updater.addon)
	bl_idname = updater.addon + ".updater_install_popup"
	bl_description = "Popup to check and display current updates available"
	bl_options = {'REGISTER', 'INTERNAL'}

	# if true, run clean install - ie remove all files before adding new
	# equivalent to deleting the addon and reinstalling, except the
	# updater folder/backup folder remains
	clean_install = bpy.props.BoolProperty(
		name="Clean install",
		description=("If enabled, completely clear the addon's folder before "
					 "installing new update, creating a fresh install"),
		default=False,
		options={'HIDDEN'}
	)

	ignore_enum = bpy.props.EnumProperty(
		name="Process update",
		description="Decide to install, ignore, or defer new addon update",
		items=[
			("install", "Update Now", "Install update now"),
			("ignore", "Ignore", "Ignore this update to prevent future popups"),
			("defer", "Defer", "Defer choice till next blender session")
		],
		options={'HIDDEN'}
	)

	def check(self, context):
		return True

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def draw(self, context):
		layout = self.layout
		if updater.invalid_updater:
			layout.label(text="Updater module error")
			return
		elif updater.update_ready:
			col = layout.column()
			col.scale_y = 0.7
			col.label(text="Update {} ready!".format(updater.update_version),
					  icon="LOOP_FORWARDS")
			col.label(text="Choose 'Update Now' & press OK to install, ",
					  icon="BLANK1")
			col.label(text="or click outside window to defer", icon="BLANK1")
			row = col.row()
			row.prop(self, "ignore_enum", expand=True)
			col.split()
		elif not updater.update_ready:
			col = layout.column()
			col.scale_y = 0.7
			col.label(text="No updates available")
			col.label(text="Press okay to dismiss dialog")
			# add option to force install
		else:
			# Case: updater.update_ready = None
			# we have not yet checked for the update.
			layout.label(text="Check for update now?")

		# Potentially in future, UI to 'check to select/revert to old version'.

	track_function = "install_update_popup"
	track_param = None
	@tracking.report_error
	def execute(self, context):
		# In case of error importing updater.
		if updater.invalid_updater:
			return {'CANCELLED'}

		if updater.manual_only:
			bpy.ops.wm.url_open(url=updater.website)
		elif updater.update_ready:

			# Action based on enum selection.
			if self.ignore_enum == 'defer':
				return {'FINISHED'}
			elif self.ignore_enum == 'ignore':
				updater.ignore_update()
				return {'FINISHED'}

			res = updater.run_update(force=False,
									 callback=post_update_callback,
									 clean=self.clean_install)

			# Should return 0, if not something happened.
			if updater.verbose:
				if res == 0:
					print("Updater returned successful")
				else:
					print("Updater returned {}, error occurred".format(res))
		elif updater.update_ready is None:
			_ = updater.check_for_update(now=True)

			# Re-launch this dialog.
			atr = AddonUpdaterInstallPopup.bl_idname.split(".")
			getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')
		else:
			updater.print_verbose("Doing nothing, not ready for update")
		return {'FINISHED'}


# User preference check-now operator
class AddonUpdaterCheckNow(bpy.types.Operator):
	bl_label = "Check now for " + updater.addon + " update"
	bl_idname = updater.addon + ".updater_check_now"
	bl_description = "Check now for an update to the {} addon".format(
		updater.addon)
	bl_options = {'REGISTER', 'INTERNAL'}

	@tracking.report_error
	def execute(self, context):
		if updater.invalid_updater:
			return {'CANCELLED'}

		if updater.async_checking and updater.error is None:
			# Check already happened.
			# Used here to just avoid constant applying settings below.
			# Ignoring if error, to prevent being stuck on the error screen.
			return {'CANCELLED'}

		# apply the UI settings
		settings = get_user_preferences(context)
		if not settings:
			updater.print_verbose(
				"Could not get {} preferences, update check skipped".format(
					__package__))
			return {'CANCELLED'}

		updater.set_check_interval(
			enabled=settings.auto_check_update,
			months=settings.updater_interval_months,
			days=settings.updater_interval_days,
			hours=settings.updater_interval_hours,
			minutes=settings.updater_interval_minutes)

		# Input is an optional callback function. This function should take a
		# bool input. If true: update ready, if false: no update ready.
		updater.check_for_update_now(ui_refresh)

		return {'FINISHED'}


class AddonUpdaterUpdateNow(bpy.types.Operator):
	bl_label = "Update " + updater.addon + " addon now"
	bl_idname = updater.addon + ".updater_update_now"
	bl_description = "Update to the latest version of the {x} addon".format(
		x=updater.addon)
	bl_options = {'REGISTER', 'INTERNAL'}

	# If true, run clean install - ie remove all files before adding new
	# equivalent to deleting the addon and reinstalling, except the updater
	# folder/backup folder remains.
	clean_install = bpy.props.BoolProperty(
		name="Clean install",
		description=("If enabled, completely clear the addon's folder before "
					 "installing new update, creating a fresh install"),
		default=False,
		options={'HIDDEN'}
	)

	track_function = "install_update"
	track_param = None
	@tracking.report_error
	def execute(self, context):

		# in case of error importing updater
		if updater.invalid_updater:
			return {'CANCELLED'}

		if updater.manual_only:
			bpy.ops.wm.url_open(url=updater.website)
		if updater.update_ready:
			# if it fails, offer to open the website instead
			try:
				res = updater.run_update(force=False,
										 callback=post_update_callback,
										 clean=self.clean_install)

				# Should return 0, if not something happened.
				if updater.verbose:
					if res == 0:
						print("Updater returned successful")
					else:
						print("Updater error response: {}".format(res))
			except Exception as expt:
				updater._error = "Error trying to run update"
				updater._error_msg = str(expt)
				updater.print_trace()
				atr = AddonUpdaterInstallManually.bl_idname.split(".")
				getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')
		elif updater.update_ready is None:
			(update_ready, version, link) = updater.check_for_update(now=True)
			# Re-launch this dialog.
			atr = AddonUpdaterInstallPopup.bl_idname.split(".")
			getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')

		elif not updater.update_ready:
			self.report({'INFO'}, "Nothing to update")
			return {'CANCELLED'}
		else:
			self.report(
				{'ERROR'}, "Encountered a problem while trying to update")
			return {'CANCELLED'}

		return {'FINISHED'}


class AddonUpdaterUpdateTarget(bpy.types.Operator):
	bl_label = updater.addon + " version target"
	bl_idname = updater.addon + ".updater_update_target"
	bl_description = "Install a targeted version of the {x} addon".format(
		x=updater.addon)
	bl_options = {'REGISTER', 'INTERNAL'}

	def target_version(self, context):
		# In case of error importing updater.
		if updater.invalid_updater:
			ret = []

		ret = []
		i = 0
		for tag in updater.tags:
			ret.append((tag, tag, "Select to install " + tag))
			i += 1
		return ret

	target = bpy.props.EnumProperty(
		name="Target version to install",
		description="Select the version to install",
		items=target_version
	)

	# If true, run clean install - ie remove all files before adding new
	# equivalent to deleting the addon and reinstalling, except the
	# updater folder/backup folder remains.
	clean_install = bpy.props.BoolProperty(
		name="Clean install",
		description=("If enabled, completely clear the addon's folder before "
					 "installing new update, creating a fresh install"),
		default=False,
		options={'HIDDEN'}
	)

	@classmethod
	def poll(cls, context):
		if updater.invalid_updater:
			return False
		return updater.update_ready is not None and len(updater.tags) > 0

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def draw(self, context):
		layout = self.layout
		if updater.invalid_updater:
			layout.label(text="Updater error")
			return
		split = layout_split(layout, factor=0.5)
		sub_col = split.column()
		sub_col.label(text="Select install version")
		sub_col = split.column()
		sub_col.prop(self, "target", text="")

	track_function = "install_update_target"
	track_param = None
	@tracking.report_error
	def execute(self, context):
		# In case of error importing updater.
		if updater.invalid_updater:
			return {'CANCELLED'}

		self.track_param = str(self.target)
		if len(self.track_param) > 13:
			self.track_param = self.track_param[:13]

		res = updater.run_update(
			force=False,
			revert_tag=self.target,
			callback=post_update_callback,
			clean=self.clean_install)

		# Should return 0, if not something happened.
		if res == 0:
			updater.print_verbose("Updater returned successful")
		else:
			updater.print_verbose(
				"Updater returned {}, , error occurred".format(res))
			return {'CANCELLED'}

		self.track_param = str(self.target)
		if len(self.track_param) > 13:
			self.track_param = self.track_param[:13]

		return {'FINISHED'}


class AddonUpdaterInstallManually(bpy.types.Operator):
	"""As a fallback, direct the user to download the addon manually"""
	bl_label = "Install update manually"
	bl_idname = updater.addon + ".updater_install_manually"
	bl_description = "Proceed to manually install update"
	bl_options = {'REGISTER', 'INTERNAL'}

	error = bpy.props.StringProperty(
		name="Error Occurred",
		default="",
		options={'HIDDEN'}
	)

	def invoke(self, context, event):
		return context.window_manager.invoke_popup(self)

	def draw(self, context):
		layout = self.layout

		if updater.invalid_updater:
			layout.label(text="Updater error")
			return

		# Display error if a prior autoamted install failed.
		if self.error != "":
			col = layout.column()
			col.scale_y = 0.7
			col.label(text="There was an issue trying to auto-install",
					  icon="ERROR")
			col.label(text="Press the download button below and install",
					  icon="BLANK1")
			col.label(text="the zip file like a normal addon.", icon="BLANK1")
		else:
			col = layout.column()
			col.scale_y = 0.7
			col.label(text="Install the addon manually")
			col.label(text="Press the download button below and install")
			col.label(text="the zip file like a normal addon.")

		# If check hasn't happened, i.e. accidentally called this menu,
		# allow to check here.

		row = layout.row()

		if updater.update_link is not None:
			row.operator(
				"wm.url_open",
				text="Direct download").url = updater.update_link
		else:
			row.operator(
				"wm.url_open",
				text="(failed to retrieve direct download)")
			row.enabled = False

			if updater.website is not None:
				row = layout.row()
				ops = row.operator("wm.url_open", text="Open website")
				ops.url = updater.website
			else:
				row = layout.row()
				row.label(text="See source website to download the update")

	def execute(self, context):
		return {'FINISHED'}


class AddonUpdaterUpdatedSuccessful(bpy.types.Operator):
	"""Addon in place, popup telling user it completed or what went wrong"""
	bl_label = "Installation Report"
	bl_idname = updater.addon + ".updater_update_successful"
	bl_description = "Update installation response"
	bl_options = {'REGISTER', 'INTERNAL', 'UNDO'}

	error = bpy.props.StringProperty(
		name="Error Occurred",
		default="",
		options={'HIDDEN'}
	)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_popup(self, event)

	def draw(self, context):
		layout = self.layout

		if updater.invalid_updater:
			layout.label(text="Updater error")
			return

		saved = updater.json
		if self.error != "":
			col = layout.column()
			col.scale_y = 0.7
			col.label(text="Error occurred, did not install", icon="ERROR")
			if updater.error_msg:
				msg = updater.error_msg
			else:
				msg = self.error
			col.label(text=str(msg), icon="BLANK1")
			rw = col.row()
			rw.scale_y = 2
			rw.operator(
				"wm.url_open",
				text="Click for manual download.",
				icon="BLANK1").url = updater.website
		elif not updater.auto_reload_post_update:
			# Tell user to restart blender after an update/restore!
			if "just_restored" in saved and saved["just_restored"]:
				col = layout.column()
				col.label(text="Addon restored", icon="RECOVER_LAST")
				alert_row = col.row()
				alert_row.alert = True
				alert_row.operator(
					"wm.quit_blender",
					text="Restart blender to reload",
					icon="BLANK1")
				updater.json_reset_restore()
			else:
				col = layout.column()
				col.label(
					text="Addon successfully installed", icon="FILE_TICK")
				alert_row = col.row()
				alert_row.alert = True
				alert_row.operator(
					"wm.quit_blender",
					text="Restart blender to reload",
					icon="BLANK1")

		else:
			# reload addon, but still recommend they restart blender
			if "just_restored" in saved and saved["just_restored"]:
				col = layout.column()
				col.scale_y = 0.7
				col.label(text="Addon restored", icon="RECOVER_LAST")
				col.label(
					text="Consider restarting blender to fully reload.",
					icon="BLANK1")
				updater.json_reset_restore()
			else:
				col = layout.column()
				col.scale_y = 0.7
				col.label(
					text="Addon successfully installed", icon="FILE_TICK")
				col.label(
					text="Consider restarting blender to fully reload.",
					icon="BLANK1")

	def execute(self, context):
		return {'FINISHED'}


class AddonUpdaterRestoreBackup(bpy.types.Operator):
	"""Restore addon from backup"""
	bl_label = "Restore backup"
	bl_idname = updater.addon + ".updater_restore_backup"
	bl_description = "Restore addon from backup"
	bl_options = {'REGISTER', 'INTERNAL'}

	@classmethod
	def poll(cls, context):
		try:
			return os.path.isdir(os.path.join(updater.stage_path, "backup"))
		except:
			return False

	@tracking.report_error
	def execute(self, context):
		# in case of error importing updater
		if updater.invalid_updater:
			return {'CANCELLED'}
		updater.restore_backup()
		return {'FINISHED'}


class AddonUpdaterIgnore(bpy.types.Operator):
	"""Ignore update to prevent future popups"""
	bl_label = "Ignore update"
	bl_idname = updater.addon + ".updater_ignore"
	bl_description = "Ignore update to prevent future popups"
	bl_options = {'REGISTER', 'INTERNAL'}

	@classmethod
	def poll(cls, context):
		if updater.invalid_updater:
			return False
		elif updater.update_ready:
			return True
		else:
			return False

	@tracking.report_error
	def execute(self, context):
		# in case of error importing updater
		if updater.invalid_updater:
			return {'CANCELLED'}
		updater.ignore_update()
		self.report({"INFO"}, "Open addon preferences for updater options")
		return {'FINISHED'}


class AddonUpdaterEndBackground(bpy.types.Operator):
	"""Stop checking for update in the background"""
	bl_label = "End background check"
	bl_idname = updater.addon + ".end_background_check"
	bl_description = "Stop checking for update in the background"
	bl_options = {'REGISTER', 'INTERNAL'}

	def execute(self, context):
		# in case of error importing updater
		if updater.invalid_updater:
			return {'CANCELLED'}
		updater.stop_async_check_update()
		return {'FINISHED'}


# -----------------------------------------------------------------------------
# Handler related, to create popups
# -----------------------------------------------------------------------------


# global vars used to prevent duplicate popup handlers
ran_auto_check_install_popup = False
ran_update_success_popup = False

# global var for preventing successive calls
ran_background_check = False


@persistent
def updater_run_success_popup_handler(scene):
	global ran_update_success_popup
	ran_update_success_popup = True

	# in case of error importing updater
	if updater.invalid_updater:
		return

	try:
		if "scene_update_post" in dir(bpy.app.handlers):
			bpy.app.handlers.scene_update_post.remove(
				updater_run_success_popup_handler)
		else:
			bpy.app.handlers.depsgraph_update_post.remove(
				updater_run_success_popup_handler)
	except:
		pass

	atr = AddonUpdaterUpdatedSuccessful.bl_idname.split(".")
	getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')


@persistent
def updater_run_install_popup_handler(scene):
	global ran_auto_check_install_popup
	ran_auto_check_install_popup = True
	updater.print_verbose("Running the install popup handler.")

	# in case of error importing updater
	if updater.invalid_updater:
		return

	try:
		if "scene_update_post" in dir(bpy.app.handlers):
			bpy.app.handlers.scene_update_post.remove(
				updater_run_install_popup_handler)
		else:
			bpy.app.handlers.depsgraph_update_post.remove(
				updater_run_install_popup_handler)
	except:
		pass

	if "ignore" in updater.json and updater.json["ignore"]:
		return  # Don't do popup if ignore pressed.
	elif "version_text" in updater.json and updater.json["version_text"].get("version"):
		version = updater.json["version_text"]["version"]
		ver_tuple = updater.version_tuple_from_text(version)

		if ver_tuple < updater.current_version:
			# User probably manually installed to get the up to date addon
			# in here. Clear out the update flag using this function.
			updater.print_verbose(
				"{} updater: appears user updated, clearing flag".format(
					updater.addon))
			updater.json_reset_restore()
			return
	atr = AddonUpdaterInstallPopup.bl_idname.split(".")
	getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')


def background_update_callback(update_ready):
	"""Passed into the updater, background thread updater"""
	global ran_auto_check_install_popup
	updater.print_verbose("Running background update callback")

	# In case of error importing updater.
	if updater.invalid_updater:
		return
	if not updater.show_popups:
		return
	if not update_ready:
		return

	# See if we need add to the update handler to trigger the popup.
	handlers = []
	if "scene_update_post" in dir(bpy.app.handlers):  # 2.7x
		handlers = bpy.app.handlers.scene_update_post
	else:  # 2.8+
		handlers = bpy.app.handlers.depsgraph_update_post
	in_handles = updater_run_install_popup_handler in handlers

	if in_handles or ran_auto_check_install_popup:
		return

	if "scene_update_post" in dir(bpy.app.handlers):  # 2.7x
		bpy.app.handlers.scene_update_post.append(
			updater_run_install_popup_handler)
	else:  # 2.8+
		bpy.app.handlers.depsgraph_update_post.append(
			updater_run_install_popup_handler)
	ran_auto_check_install_popup = True
	updater.print_verbose("Attempted popup prompt")


def post_update_callback(module_name, res=None):
	"""Callback for once the run_update function has completed.

	Only makes sense to use this if "auto_reload_post_update" == False,
	i.e. don't auto-restart the addon.

	Arguments:
		module_name: returns the module name from updater, but unused here.
		res: If an error occurred, this is the detail string.
	"""

	# In case of error importing updater.
	if updater.invalid_updater:
		return

	if res is None:
		# This is the same code as in conditional at the end of the register
		# function, ie if "auto_reload_post_update" == True, skip code.
		updater.print_verbose(
			"{} updater: Running post update callback".format(updater.addon))

		atr = AddonUpdaterUpdatedSuccessful.bl_idname.split(".")
		getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')
		global ran_update_success_popup
		ran_update_success_popup = True
	else:
		# Some kind of error occurred and it was unable to install, offer
		# manual download instead.
		atr = AddonUpdaterUpdatedSuccessful.bl_idname.split(".")
		getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT', error=res)
	return


def ui_refresh(update_status):
	"""Redraw the ui once an async thread has completed"""
	for windowManager in bpy.data.window_managers:
		for window in windowManager.windows:
			for area in window.screen.areas:
				area.tag_redraw()


def check_for_update_background():
	"""Function for asynchronous background check.

	*Could* be called on register, but would be bad practice as the bare
	minimum code should run at the moment of registration (addon ticked).
	"""
	if updater.invalid_updater:
		return
	global ran_background_check
	if ran_background_check:
		# Global var ensures check only happens once.
		return
	elif updater.update_ready is not None or updater.async_checking:
		# Check already happened.
		# Used here to just avoid constant applying settings below.
		return

	# Apply the UI settings.
	settings = get_user_preferences(bpy.context)
	if not settings:
		return
	updater.set_check_interval(enabled=settings.auto_check_update,
							   months=settings.updater_interval_months,
							   days=settings.updater_interval_days,
							   hours=settings.updater_interval_hours,
							   minutes=settings.updater_interval_minutes)

	# Input is an optional callback function. This function should take a bool
	# input, if true: update ready, if false: no update ready.
	updater.check_for_update_async(background_update_callback)
	ran_background_check = True


def check_for_update_nonthreaded(self, context):
	"""Can be placed in front of other operators to launch when pressed"""
	if updater.invalid_updater:
		return

	# Only check if it's ready, ie after the time interval specified should
	# be the async wrapper call here.
	settings = get_user_preferences(bpy.context)
	if not settings:
		if updater.verbose:
			print("Could not get {} preferences, update check skipped".format(
				__package__))
		return
	updater.set_check_interval(enabled=settings.auto_check_update,
							   months=settings.updater_interval_months,
							   days=settings.updater_interval_days,
							   hours=settings.updater_interval_hours,
							   minutes=settings.updater_interval_minutes)

	(update_ready, version, link) = updater.check_for_update(now=False)
	if update_ready:
		atr = AddonUpdaterInstallPopup.bl_idname.split(".")
		getattr(getattr(bpy.ops, atr[0]), atr[1])('INVOKE_DEFAULT')
	else:
		updater.print_verbose("No update ready")
		self.report({'INFO'}, "No update ready")


def show_reload_popup():
	"""For use in register only, to show popup after re-enabling the addon.

	Must be enabled by developer.
	"""
	if updater.invalid_updater:
		return
	saved_state = updater.json
	global ran_update_success_popup

	has_state = saved_state is not None
	just_updated = "just_updated" in saved_state
	updated_info = saved_state["just_updated"]

	if not (has_state and just_updated and updated_info):
		return

	updater.json_reset_postupdate()  # So this only runs once.

	# No handlers in this case.
	if not updater.auto_reload_post_update:
		return

	# See if we need add to the update handler to trigger the popup.
	handlers = []
	if "scene_update_post" in dir(bpy.app.handlers):  # 2.7x
		handlers = bpy.app.handlers.scene_update_post
	else:  # 2.8+
		handlers = bpy.app.handlers.depsgraph_update_post
	in_handles = updater_run_success_popup_handler in handlers

	if in_handles or ran_update_success_popup:
		return

	if "scene_update_post" in dir(bpy.app.handlers):  # 2.7x
		bpy.app.handlers.scene_update_post.append(
			updater_run_success_popup_handler)
	else:  # 2.8+
		bpy.app.handlers.depsgraph_update_post.append(
			updater_run_success_popup_handler)
	ran_update_success_popup = True


# -----------------------------------------------------------------------------
# Example UI integrations
# -----------------------------------------------------------------------------
def update_notice_box_ui(self, context):
	"""Update notice draw, to add to the end or beginning of a panel.

	After a check for update has occurred, this function will draw a box
	saying an update is ready, and give a button for: update now, open website,
	or ignore popup. Ideal to be placed at the end / beginning of a panel.
	"""

	if updater.invalid_updater:
		return

	saved_state = updater.json
	if not updater.auto_reload_post_update:
		if "just_updated" in saved_state and saved_state["just_updated"]:
			layout = self.layout
			box = layout.box()
			col = box.column()
			alert_row = col.row()
			alert_row.alert = True
			alert_row.operator(
				"wm.quit_blender",
				text="Restart blender",
				icon="ERROR")
			col.label(text="to complete update")
			return

	# If user pressed ignore, don't draw the box.
	if "ignore" in updater.json and updater.json["ignore"]:
		return
	if not updater.update_ready:
		return

	layout = self.layout
	box = layout.box()
	col = box.column(align=True)
	col.alert = True
	col.label(text="Update ready!", icon="ERROR")
	col.alert = False
	col.separator()
	row = col.row(align=True)
	split = row.split(align=True)
	colL = split.column(align=True)
	colL.scale_y = 1.5
	colL.operator(AddonUpdaterIgnore.bl_idname, icon="X", text="Ignore")
	colR = split.column(align=True)
	colR.scale_y = 1.5
	if not updater.manual_only:
		colR.operator(AddonUpdaterUpdateNow.bl_idname,
					  text="Update", icon="LOOP_FORWARDS")
		col.operator("wm.url_open", text="Open website").url = updater.website
		# ops = col.operator("wm.url_open",text="Direct download")
		# ops.url=updater.update_link
		col.operator(AddonUpdaterInstallManually.bl_idname,
					 text="Install manually")
	else:
		# ops = col.operator("wm.url_open", text="Direct download")
		# ops.url=updater.update_link
		col.operator("wm.url_open", text="Get it now").url = updater.website


def update_settings_ui(self, context, element=None):
	"""Preferences - for drawing with full width inside user preferences

	A function that can be run inside user preferences panel for prefs UI.
	Place inside UI draw using:
		addon_updater_ops.update_settings_ui(self, context)
	or by:
		addon_updater_ops.update_settings_ui(context)
	"""

	# Element is a UI element, such as layout, a row, column, or box.
	if element is None:
		element = self.layout
	box = element.box()

	# In case of error importing updater.
	if updater.invalid_updater:
		box.label(text="Error initializing updater code:")
		box.label(text=updater.error_msg)
		return
	settings = get_user_preferences(context)
	if not settings:
		box.label(text="Error getting updater preferences", icon='ERROR')
		return

	# auto-update settings
	box.label(text="Updater Settings")
	row = box.row()

	# special case to tell user to restart blender, if set that way
	if not updater.auto_reload_post_update:
		saved_state = updater.json
		if "just_updated" in saved_state and saved_state["just_updated"]:
			row.alert = True
			row.operator("wm.quit_blender",
						 text="Restart blender to complete update",
						 icon="ERROR")
			return

	split = layout_split(row, factor=0.4)
	sub_col = split.column()
	sub_col.prop(settings, "auto_check_update")
	sub_col = split.column()

	if not settings.auto_check_update:
		sub_col.enabled = False
	sub_row = sub_col.row()
	sub_row.label(text="Interval between checks")
	sub_row = sub_col.row(align=True)
	check_col = sub_row.column(align=True)
	check_col.prop(settings, "updater_interval_months")
	check_col = sub_row.column(align=True)
	check_col.prop(settings, "updater_interval_days")
	check_col = sub_row.column(align=True)

	# Consider un-commenting for local dev (e.g. to set shorter intervals)
	# check_col.prop(settings,"updater_interval_hours")
	# check_col = sub_row.column(align=True)
	# check_col.prop(settings,"updater_interval_minutes")

	# Checking / managing updates.
	row = box.row()
	col = row.column()
	if updater.error is not None:
		sub_col = col.row(align=True)
		sub_col.scale_y = 1
		split = sub_col.split(align=True)
		split.scale_y = 2
		if "ssl" in updater.error_msg.lower():
			split.enabled = True
			split.operator(AddonUpdaterInstallManually.bl_idname,
						   text=updater.error)
		else:
			split.enabled = False
			split.operator(AddonUpdaterCheckNow.bl_idname,
						   text=updater.error)
		split = sub_col.split(align=True)
		split.scale_y = 2
		split.operator(AddonUpdaterCheckNow.bl_idname,
					   text="", icon="FILE_REFRESH")

	elif updater.update_ready is None and not updater.async_checking:
		col.scale_y = 2
		col.operator(AddonUpdaterCheckNow.bl_idname)
	elif updater.update_ready is None:  # async is running
		sub_col = col.row(align=True)
		sub_col.scale_y = 1
		split = sub_col.split(align=True)
		split.enabled = False
		split.scale_y = 2
		split.operator(AddonUpdaterCheckNow.bl_idname, text="Checking...")
		split = sub_col.split(align=True)
		split.scale_y = 2
		split.operator(AddonUpdaterEndBackground.bl_idname, text="", icon="X")

	elif updater.include_branches and \
			len(updater.tags) == len(updater.include_branch_list) and not \
			updater.manual_only:
		# No releases found, but still show the appropriate branch.
		sub_col = col.row(align=True)
		sub_col.scale_y = 1
		split = sub_col.split(align=True)
		split.scale_y = 2
		update_now_txt = "Update directly to {}".format(
			updater.include_branch_list[0])
		split.operator(AddonUpdaterUpdateNow.bl_idname, text=update_now_txt)
		split = sub_col.split(align=True)
		split.scale_y = 2
		split.operator(AddonUpdaterCheckNow.bl_idname,
					   text="", icon="FILE_REFRESH")

	elif updater.update_ready and not updater.manual_only:
		sub_col = col.row(align=True)
		sub_col.scale_y = 1
		split = sub_col.split(align=True)
		split.scale_y = 2
		split.operator(AddonUpdaterUpdateNow.bl_idname,
					   text="Update now to " + str(updater.update_version))
		split = sub_col.split(align=True)
		split.scale_y = 2
		split.operator(AddonUpdaterCheckNow.bl_idname,
					   text="", icon="FILE_REFRESH")

	elif updater.update_ready and updater.manual_only:
		col.scale_y = 2
		dl_now_txt = "Download " + str(updater.update_version)
		col.operator("wm.url_open",
					 text=dl_now_txt).url = updater.website
	else:  # i.e. that updater.update_ready == False.
		sub_col = col.row(align=True)
		sub_col.scale_y = 1
		split = sub_col.split(align=True)
		split.enabled = False
		split.scale_y = 2
		split.operator(AddonUpdaterCheckNow.bl_idname,
					   text="Addon is up to date")
		split = sub_col.split(align=True)
		split.scale_y = 2
		split.operator(AddonUpdaterCheckNow.bl_idname,
					   text="", icon="FILE_REFRESH")

	if not updater.manual_only:
		col = row.column(align=True)
		if updater.include_branches and len(updater.include_branch_list) > 0:
			branch = updater.include_branch_list[0]
			col.operator(AddonUpdaterUpdateTarget.bl_idname,
						 text="Install {} / old version".format(branch))
		else:
			col.operator(AddonUpdaterUpdateTarget.bl_idname,
						 text="(Re)install addon version")
		last_date = "none found"
		backup_path = os.path.join(updater.stage_path, "backup")
		if "backup_date" in updater.json and os.path.isdir(backup_path):
			if updater.json["backup_date"] == "":
				last_date = "Date not found"
			else:
				last_date = updater.json["backup_date"]
		backup_text = "Restore addon backup ({})".format(last_date)
		col.operator(AddonUpdaterRestoreBackup.bl_idname, text=backup_text)

	row = box.row()
	row.scale_y = 0.7
	last_check = updater.json["last_check"]
	if updater.error is not None and updater.error_msg is not None:
		row.label(text=updater.error_msg)
	elif last_check:
		last_check = last_check[0: last_check.index(".")]
		row.label(text="Last update check: " + last_check)
	else:
		row.label(text="Last update check: Never")


def update_settings_ui_condensed(self, context, element=None):
	"""Preferences - Condensed drawing within preferences.

	Alternate draw for user preferences or other places, does not draw a box.
	"""

	# Element is a UI element, such as layout, a row, column, or box.
	if element is None:
		element = self.layout
	row = element.row()

	# In case of error importing updater.
	if updater.invalid_updater:
		row.label(text="Error initializing updater code:")
		row.label(text=updater.error_msg)
		return
	settings = get_user_preferences(context)
	if not settings:
		row.label(text="Error getting updater preferences", icon='ERROR')
		return

	# Special case to tell user to restart blender, if set that way.
	if not updater.auto_reload_post_update:
		saved_state = updater.json
		if "just_updated" in saved_state and saved_state["just_updated"]:
			row.alert = True  # mark red
			row.operator(
				"wm.quit_blender",
				text="Restart blender to complete update",
				icon="ERROR")
			return

	col = row.column()
	if updater.error is not None:
		sub_col = col.row(align=True)
		sub_col.scale_y = 1
		split = sub_col.split(align=True)
		split.scale_y = 2
		if "ssl" in updater.error_msg.lower():
			split.enabled = True
			split.operator(AddonUpdaterInstallManually.bl_idname,
						   text=updater.error)
		else:
			split.enabled = False
			split.operator(AddonUpdaterCheckNow.bl_idname,
						   text=updater.error)
		split = sub_col.split(align=True)
		split.scale_y = 2
		split.operator(AddonUpdaterCheckNow.bl_idname,
					   text="", icon="FILE_REFRESH")

	elif updater.update_ready is None and not updater.async_checking:
		col.scale_y = 2
		col.operator(AddonUpdaterCheckNow.bl_idname)
	elif updater.update_ready is None:  # Async is running.
		sub_col = col.row(align=True)
		sub_col.scale_y = 1
		split = sub_col.split(align=True)
		split.enabled = False
		split.scale_y = 2
		split.operator(AddonUpdaterCheckNow.bl_idname, text="Checking...")
		split = sub_col.split(align=True)
		split.scale_y = 2
		split.operator(AddonUpdaterEndBackground.bl_idname, text="", icon="X")

	elif updater.include_branches and \
			len(updater.tags) == len(updater.include_branch_list) and not \
			updater.manual_only:
		# No releases found, but still show the appropriate branch.
		sub_col = col.row(align=True)
		sub_col.scale_y = 1
		split = sub_col.split(align=True)
		split.scale_y = 2
		now_txt = "Update directly to " + str(updater.include_branch_list[0])
		split.operator(AddonUpdaterUpdateNow.bl_idname, text=now_txt)
		split = sub_col.split(align=True)
		split.scale_y = 2
		split.operator(AddonUpdaterCheckNow.bl_idname,
					   text="", icon="FILE_REFRESH")

	elif updater.update_ready and not updater.manual_only:
		sub_col = col.row(align=True)
		sub_col.scale_y = 1
		split = sub_col.split(align=True)
		split.scale_y = 2
		split.operator(AddonUpdaterUpdateNow.bl_idname,
					   text="Update now to " + str(updater.update_version))
		split = sub_col.split(align=True)
		split.scale_y = 2
		split.operator(AddonUpdaterCheckNow.bl_idname,
					   text="", icon="FILE_REFRESH")

	elif updater.update_ready and updater.manual_only:
		col.scale_y = 2
		dl_txt = "Download " + str(updater.update_version)
		col.operator("wm.url_open", text=dl_txt).url = updater.website
	else:  # i.e. that updater.update_ready == False.
		sub_col = col.row(align=True)
		sub_col.scale_y = 1
		split = sub_col.split(align=True)
		split.enabled = False
		split.scale_y = 2
		split.operator(AddonUpdaterCheckNow.bl_idname,
					   text="Addon is up to date")
		split = sub_col.split(align=True)
		split.scale_y = 2
		split.operator(AddonUpdaterCheckNow.bl_idname,
					   text="", icon="FILE_REFRESH")

	row = element.row()
	row.prop(settings, "auto_check_update")

	row = element.row()
	row.scale_y = 0.7
	last_check = updater.json["last_check"]
	if updater.error is not None and updater.error_msg is not None:
		row.label(text=updater.error_msg)
	elif last_check != "" and last_check is not None:
		last_check = last_check[0: last_check.index(".")]
		row.label(text="Last check: " + last_check)
	else:
		row.label(text="Last check: Never")


def skip_tag_function(self, tag):
	"""A global function for tag skipping.

	A way to filter which tags are displayed, e.g. to limit downgrading too
	long ago.

	Args:
		self: The instance of the singleton addon update.
		tag: the text content of a tag from the repo, e.g. "v1.2.3".

	Returns:
		bool: True to skip this tag name (ie don't allow for downloading this
			version), or False if the tag is allowed.
	"""

	# In case of error importing updater.
	if self.invalid_updater:
		return False

	# ---- write any custom code here, return true to disallow version ---- #
	#
	# # Filter out e.g. if 'beta' is in name of release
	# if 'beta' in tag.lower():
	# 	return True
	# ---- write any custom code above, return true to disallow version --- #
	
	# Ignore release candidates
	skip_if_present = ['rc', 'alpha', 'beta']
	for skip_name in skip_if_present:
		if skip_name in tag.lower():
			return True

	if self.include_branches:
		for branch in self.include_branch_list:
			if tag["name"].lower() == branch:
				return False

	# Function converting string to tuple, ignoring e.g. leading 'v'.
	# Be aware that this strips out other text that you might otherwise
	# want to be kept and accounted for when checking tags (e.g. v1.1a vs 1.1b)
	tupled = self.version_tuple_from_text(tag["name"])
	if not isinstance(tupled, tuple):
		return True

	# Select the min tag version - change tuple accordingly.
	if self.version_min_update is not None:
		if tupled < self.version_min_update:
			return True  # Skip if current version below this.

	# Select the max tag version.
	if self.version_max_update is not None:
		if tupled >= self.version_max_update:
			return True  # Skip if current version at or above this.

	# In all other cases, allow showing the tag for updating/reverting.
	# To simply and always show all tags, this return False could be moved
	# to the start of the function definition so all tags are allowed.
	return False


def select_link_function(self, tag):
	"""Only customize if trying to leverage "attachments" in *GitHub* releases.

	A way to select from one or multiple attached downloadable files from the
	server, instead of downloading the default release/tag source code.
	"""

	# -- Default, universal case (and is the only option for GitLab/Bitbucket)
	link = tag["zipball_url"]

	# -- Example: select the first (or only) asset instead source code --
	# if "assets" in tag and "browser_download_url" in tag["assets"][0]:
	# 	link = tag["assets"][0]["browser_download_url"]

	# -- Example: select asset based on OS, where multiple builds exist --
	# # not tested/no error checking, modify to fit your own needs!
	# # assume each release has three attached builds:
	# #		release_windows.zip, release_OSX.zip, release_linux.zip
	# # This also would logically not be used with "branches" enabled
	# if platform.system() == "Darwin": # ie OSX
	# 	link = [asset for asset in tag["assets"] if 'OSX' in asset][0]
	# elif platform.system() == "Windows":
	# 	link = [asset for asset in tag["assets"] if 'windows' in asset][0]
	# elif platform.system() == "Linux":
	# 	link = [asset for asset in tag["assets"] if 'linux' in asset][0]

	return link


# -----------------------------------------------------------------------------
# Register, should be run in the register module itself
# -----------------------------------------------------------------------------
classes = (
	AddonUpdaterInstallPopup,
	AddonUpdaterCheckNow,
	AddonUpdaterUpdateNow,
	AddonUpdaterUpdateTarget,
	AddonUpdaterInstallManually,
	AddonUpdaterUpdatedSuccessful,
	AddonUpdaterRestoreBackup,
	AddonUpdaterIgnore,
	AddonUpdaterEndBackground
)


def register(bl_info):
	"""Registering the operators in this module"""
	from . import conf
	updater.verbose = conf.env.verbose

	# safer failure in case of issue loading module
	if updater.error != None:
		print("Exiting updater registration, error return")
		return
	if updater.update_ready is None:  # Force clear out after blender restart.
		saved_state = updater.json
		if saved_state.get("just_updated") is True:
			updater.json_reset_postupdate()
	updater.clear_state()  # Clear internal vars, avoids reloading oddities.

	updater.engine = "Github"
	updater.user = "theduckcow"
	updater.repo = "mcprep"
	updater.website = "https://theduckcow.com/dev/blender/mcprep-download/"
	updater.subfolder_path = "MCprep_addon/"
	updater.current_version = bl_info["version"]
	updater.backup_current = True
	updater.backup_ignore_patterns = ["__pycache__"]
	updater.overwrite_patterns = ["*.png", "README.md", "*.txt", "*.blend"]
	updater.remove_pre_update_patterns = [
		"*.py", "*.pyc", "mcprep_addon_tracker.json", "mcprep_data.json"]
	updater.include_branches = False
	updater.include_branch_list = None  # is the equivalent to setting ['master']
	updater.manual_only = False # used to be True
	updater.fake_install = False # Set to true to test callback/reloading

	min_ver = (3,0,0)
	if hasattr(bpy.app, "version") and bpy.app.version >= (2, 80):
		min_ver = (3,2,0)
	updater.version_min_update = min_ver
	updater.version_max_update = None
	updater.version_max_update = None  # if not wanting to define a max
	updater.skip_tag = skip_tag_function # min and max used in this function
	updater.use_releases = True
	updater.select_link = select_link_function # will select asset


	# The register line items for all operators/panels
	# If using bpy.utils.register_module(__name__) to register elsewhere
	# in the addon, delete these lines (also from unregister)
	for cls in classes:
		# apply annotations to remove Blender 2.8 warnings, no effect on 2.7
		make_annotations(cls)
		# comment out this line if using bpy.utils.register_module(__name__)
		bpy.utils.register_class(cls)

	# showReloadPopup()


def unregister():
	for cls in reversed(classes):
		# Comment out this line if using bpy.utils.unregister_module(__name__).
		bpy.utils.unregister_class(cls)

	# Clear global vars since they may persist if not restarting blender.
	updater.clear_state()  # Clear internal vars, avoids reloading oddities.

	global ran_auto_check_install_popup
	ran_auto_check_install_popup = False

	global ran_update_success_popup
	ran_update_success_popup = False

	global ran_background_check
	ran_background_check = False
