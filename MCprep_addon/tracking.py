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


import os
import re
import traceback
import json
import http.client
import platform
import threading
import textwrap
from datetime import datetime

import bpy

from . import conf


# -----------------------------------------------------------------------------
# global vars
# -----------------------------------------------------------------------------

IDNAME = "mcprep"

# max data/string lengths to match server-side validation,
# if exceeded, request will return denied (no data written)
SHORT_FIELD_MAX = 64
USER_COMMENT_LENGTH = 512
ERROR_STRING_LENGTH = 1024

# -----------------------------------------------------------------------------
# primary class implementation
# -----------------------------------------------------------------------------


class Singleton_tracking(object):

	def __init__(self):
		self._verbose = False
		self._tracking_enabled = False
		self._appurl = ""
		self._failsafe = False
		self._dev = False
		self._port = 443
		self._background = False
		self._bg_thread = []
		self._version = ""
		self._addon = __package__.lower()
		self._tracker_json = os.path.join(os.path.dirname(__file__),
							self._addon+"_tracker.json")
		self._tracker_idbackup = os.path.join(os.path.dirname(__file__),
							os.pardir,self._addon+"_trackerid.json")
		self._handling_error = False
		self.json = {}


	# -------------------------------------------------------------------------
	# Getters and setters
	# -------------------------------------------------------------------------

	@property
	def tracking_enabled(self):
		return self._tracking_enabled
	@tracking_enabled.setter
	def tracking_enabled(self, value):
		self._tracking_enabled = bool(value)
		self.enable_tracking(False, value)

	@property
	def verbose(self):
		return self._verbose
	@verbose.setter
	def verbose(self, value):
		try:
			self._verbose = bool(value)
		except:
			raise ValueError("Verbose must be a boolean value")

	@property
	def appurl(self):
		return self._appurl
	@appurl.setter
	def appurl(self, value):
		if value[-1] == "/":
			value = value[:-1]
		self._appurl = value

	@property
	def failsafe(self):
		return self._failsafe
	@failsafe.setter
	def failsafe(self, value):
		try:
			self._failsafe = bool(value)
		except:
			raise ValueError("failsafe must be a boolean value")

	@property
	def dev(self):
		return self._dev
	@dev.setter
	def dev(self, value):
		try:
			self._dev = bool(value)
		except:
			raise ValueError("background must be a boolean value")

	@property
	def background(self):
		return self._background
	@background.setter
	def background(self, value):
		try:
			self._background = bool(value)
		except:
			raise ValueError("background must be a boolean value")

	@property
	def version(self):
		return self._version
	@version.setter
	def version(self, value):
		self._version = value

	@property
	def addon(self):
		return self._addon
	@addon.setter
	def addon(self, value):
		self._addon = value

	# number/settings for frequency use before ask for enable tracking

	# -------------------------------------------------------------------------
	# Public functions
	# -------------------------------------------------------------------------

	def enable_tracking(self, toggle=True, enable=True):
		# respect toggle primarily
		if toggle:
			self._tracking_enabled = not self._tracking_enabled
		else:
			self._tracking_enabled = enable

		# update static json
		self.json["enable_tracking"] = self._tracking_enabled
		self.save_tracker_json()

	def initialize(self, appurl, version):
		""" Load the enable_tracking-preference (ie in or out),
		and create tracker data"""
		self._appurl = appurl
		self._version = version
		# create the local file
		# push into BG push update info if true
		# create local cache file locations
		# including search for previous
		self.set_tracker_json()
		return

	def request(self, method, path, payload, background=False, callback=None):
		"""Interface request, either launches on main or a background thread."""
		if method not in ["POST", "PUT", "GET"]:
			raise ValueError("Method must be POST, PUT, or GET")
		if background is False:
			return self.raw_request(method, path, payload, callback)
		else:
			if self._verbose: print("Starting background thread")
			bg_thread = threading.Thread(target=self.raw_request, args=(method, path, payload, callback))
			bg_thread.daemon = True
			#self._bg_threads.append(bg_thread)
			bg_thread.start()
			return "Thread launched"

	def raw_request(self, method, path, payload, callback=None):
		# raw request, may be in background thread or main
		# convert url into domain
		url = self._appurl.split("//")[1]
		url = url.split("/")[0]

		connection = http.client.HTTPSConnection(url, self._port)
		try:
			connection.connect()
			if self.verbose:
				print(self._addon + ": Connection made to "+str(path))
		except:
			print(self._addon + ": Connection failed, intended report destination: "+str(path))
			return {'status':'NO_CONNECTION'}

		if method=="POST" or method=="PUT":
			connection.request(method, path, payload)
		elif method == "GET":
			connection.request(method, path)
		else:
			raise ValueError("raw_request input must be GET, POST, or PUT")

		raw = connection.getresponse().read()
		resp = json.loads(raw.decode())
		if self._verbose: print("Response: "+str(resp))

		if callback != None:
			if self._verbose: print("Running callback")
			callback(resp)

		return resp

	def set_tracker_json(self):
		if self._tracker_json is None:
			raise ValueError("tracker_json is not defined")

		if os.path.isfile(self._tracker_json) is True:
			with open(self._tracker_json) as data_file:
				self.json = json.load(data_file)
				if self._verbose: print("Read in json settings from tracker file")
		else:
			# set data structure
			self.json = {
				"install_date":None,
				"install_id":None,
				"enable_tracking":False,
				"status":None,
				"metadata":{}
			}

			if os.path.isfile(self._tracker_idbackup):
				with open(self._tracker_idbackup) as data_file:
					idbackup = json.load(data_file)
					if self._verbose: print("Reinstall, getting IDNAME")
					if "IDNAME" in idbackup:
						self.json["install_id"] = idbackup["IDNAME"]
						self.json["status"] = "re-install"
						self.json["install_date"] = idbackup["date"]

			self.save_tracker_json()

		# update any other properties if necessary from json
		self._tracking_enabled = self.json["enable_tracking"]

	def save_tracker_json(self):
		"""Save out current state of the tracker json to file."""
		jpath = self._tracker_json
		outf = open(jpath, 'w')
		data_out = json.dumps(self.json, indent=4)
		outf.write(data_out)
		outf.close()
		if self._verbose:
			print("Wrote out json settings to file, with the contents:")
			print(self.json)

	def save_tracker_idbackup(self):
		"""Save copy of the ID file to parent folder location, for detecting
		reinstalls in the future if the folder is deleted"""
		jpath = self._tracker_idbackup

		if "install_id" in self.json and self.json["install_id"] != None:
			outf = open(jpath, 'w')
			idbackup = {"IDNAME":self.json["install_id"],
						"date":self.json["install_date"]}
			data_out = json.dumps(idbackup,indent=4)
			outf.write(data_out)
			outf.close()
			if self._verbose:
				print("Wrote out backup settings to file, with the contents:")
				print(idbackup)

	def remove_indentifiable_information(self, report):
		"""Remove filepath from report logs, which could have included
		sensitive information such as usernames or names"""
		return re.sub(
				r'(?i)File "[/\\]{1,2}.*[/\\]{1,2}',
				'File "<addon_path>'+os.sep,
				report)


# -----------------------------------------------------------------------------
# Create the Singleton instance
# -----------------------------------------------------------------------------


Tracker = Singleton_tracking()


# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------


class toggle_enable_tracking(bpy.types.Operator):
	"""Enabled or disable usage tracking"""
	bl_idname = IDNAME+".toggle_enable_tracking"
	bl_label = "Toggle opt-in for analytics tracking"
	bl_description = "Toggle anonymous usage tracking to help the developers. "+\
			" The only data tracked is what MCprep functions are used, key "+\
			"blender/addon information, and the timestamp of the addon installation"
	options = {'REGISTER', 'UNDO'}

	tracking = bpy.props.EnumProperty(
		items = [('toggle', 'Toggle', 'Toggle operator use tracking'),
				('enable', 'Enable', 'Enable operator use tracking'),
				('disable', 'Disable', 'Disable operator use tracking (if already on)')],
		name = "tracking")

	def execute(self, context):
		if self.tracking == "toggle":
			Tracker.enable_tracking(toggle=True)
		elif self.tracking == "enable":
			Tracker.enable_tracking(toggle=False, enable=True)
		else:
			Tracker.enable_tracking(toggle=False, enable=False)
		return {'FINISHED'}


class popup_feedback(bpy.types.Operator):
	bl_idname = IDNAME+".popup_feedback"
	bl_label = "Thanks for using {}!".format(IDNAME)
	bl_description = "Take a survey to give feedback about the addon"
	options = {'REGISTER', 'UNDO'}

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self, width=400)

	def draw(self, context):

		self.layout.split()
		col = self.layout.column()
		col.alignment='CENTER'
		col.scale_y = 0.7
		col.label("Want to help out even more?")
		col.label("Press OK below to open the MCprep survey")
		col.label("Responding helps direct development time,")
		col.label("and identify those nasty bugs.")
		col.label("You help everyone by responding!")

	def execute(self, context):
		bpy.ops.wm.url_open(url="bit.ly/MCprepSurvey")

		return {'FINISHED'}


class popup_report_error(bpy.types.Operator):
	bl_idname = IDNAME+".report_error"
	bl_label = "MCprep ERROR OCCURED"
	bl_description = "Report error to database, add additional comments for context"

	error_report = bpy.props.StringProperty(default="")
	comment = bpy.props.StringProperty(
		default="",
		maxlen=USER_COMMENT_LENGTH,
		options={'SKIP_SAVE'})

	action = bpy.props.EnumProperty(
		items = [('report', 'Send', 'Send the error report to developers, fully anonymous'),
				('ignore', "Don't send", "Ignore this error report")],
		)

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self, width=500)

	def draw_header(self, context):
		self.layout.label(text="", icon="ERROR") # doesn't work/add to draw

	def draw(self, context):
		layout = self.layout
		try:
			bversion = str(bpy.app.version)
		except:
			bversion = "unknown"

		col = layout.column()
		col.label("Error detected, press OK below to send to developer", icon="ERROR")
		box = col.box()
		boxcol = box.column()
		boxcol.scale_y = 0.7
		if self.error_report=="":
			box.label(" # no error code identified # ")
		else:
			width = 500
			report_lines = self.error_report.split("\n")[:-1]
			tot_ln = 0
			max_ln = 10
			for ln in report_lines:
				sub_lns = textwrap.fill(ln, width-30)
				spl = sub_lns.split("\n")
				for i,s in enumerate(spl):
					boxcol.label(s)
					tot_ln+=1
					if tot_ln==max_ln: break
				if tot_ln==max_ln: break
		boxcol.label("."*500)
		# boxcol.label("System & addon information:")
		sysinfo="Blender version: {}\nMCprep version: {}\nOS: {}\n MCprep install identifier: {}".format(
				bversion,
				Tracker.version,
				get_platform_details(),
				Tracker.json["install_id"],
		)
		for ln in sysinfo.split("\n"):
			boxcol.label(ln)

		col.label("(Optional) Describe what you were trying to do when the error occured:")
		col.prop(self,"comment",text="")

		row = col.row(align=True)
		# spl = layout.split(percentage=80)
		split = layout.split(percentage=0.6)
		spcol = split.row()
		spcol.label("Select 'Send' then press OK to share anonymous report")
		split_two = split.split(percentage=0.4)
		spcol_two = split_two.row(align=True)
		spcol_two.prop(self,"action",text="")
		spcol_two = split_two.row(align=True)
		p = spcol_two.operator("wm.url_open", text="How is this used?", icon="QUESTION")
		p.url = "http://theduckcow.com/dev/blender/mcprep/reporting-errors/"

	def execute(self, context):

		if self.action=="ignore":
			return {"FINISHED"}
		# also do followup callback for hey, check here for issues or support?
		report = {"error":self.error_report,"user_comment":self.comment}
		if self.action == 'report':
			res = logError(report)
			if Tracker.verbose:
				print("Logged user report, with server response:")
				print(res)
			self.report({"INFO"},"Thanks for sharing the report")

		return {'FINISHED'}


# -----------------------------------------------------------------------------
# additional functions
# -----------------------------------------------------------------------------


def trackInstalled(background=None):
	"""Send new install event to database"""

	# if already installed, skip
	if Tracker.json["status"] == None and \
			Tracker.json["install_id"] != None: return

	if Tracker.verbose: print("Tracking install")

	# if no override set, use default
	if background == None:
		background = Tracker.background

	def runInstall(background):

		if Tracker.dev is True:
			location = "/1/track/install_dev.json"
		else:
			location = "/1/track/install.json"

		# for compatibility to prior blender (2.75?)
		try:
			bversion = str(bpy.app.version)
		except:
			bversion = "unknown"

		# capture re-installs/other status events
		if Tracker.json["status"]==None:
			status = "New install"
		else:
			status = Tracker.json["status"]
			Tracker.json["status"]=None
			Tracker.save_tracker_json()

		Tracker.json["install_date"] = str(datetime.now())
		payload = json.dumps({
				"timestamp": {".sv": "timestamp"},
				"usertime":Tracker.json["install_date"],
				"version":Tracker.version,
				"blender":bversion,
				"status":status,
				"platform":get_platform_details()
			})

		resp = Tracker.request('POST', location, payload, background, callback)

	def callback(arg):
		# assumes input is the server response (dictionary format)
		if type(arg) != type({'name':'ID'}):
			return
		elif "name" not in arg:
			return

		Tracker.json["install_id"] = arg["name"]
		Tracker.save_tracker_json()
		Tracker.save_tracker_idbackup()

	if Tracker.failsafe is True:
		try:
			runInstall(background)
		except:
			pass
	else:
		runInstall(background)


def trackUsage(function, param=None, background=None):
	"""Send usage operator usage + basic metadata to database"""

	if Tracker.tracking_enabled is False: return # skip if not opted in
	if conf.internal_change is True: return # skip if internal run

	if Tracker.verbose: print("Tracking usage: "+function +", param: "+str(param))

	# if no override set, use default
	if background == None:
		background = Tracker.background

	def runUsage(background):

		if Tracker.dev is True:
			location = "/1/track/usage_dev.json"
		else:
			location = "/1/track/usage.json"

		# for compatibility to prior blender (2.75?)
		try:
			bversion = str(bpy.app.version)
		except:
			bversion = "unknown"

		payload = json.dumps({
				"timestamp":{".sv": "timestamp"},
				"version":Tracker.version,
				"blender":bversion,
				"platform":get_platform_details(),
				"function":function,
				"param":str(param),
				"ID":Tracker.json["install_id"]
			})
		print(payload)
		resp = Tracker.request('POST', location, payload, background)

	if Tracker.failsafe is True:
		try:
			runUsage(background)
		except:
			pass
	else:
		runUsage(background)


def logError(report, background=None):
	"""Send error report to database"""

	# if no override set, use default
	if background == None: background = Tracker.background

	def runError(background):
		# ie auto sent in background, must adhere to tracking usage
		if Tracker.tracking_enabled is False: return # skip if not opted in

		if Tracker.dev is True:
			location = "/1/log/user_report_dev.json"
		else:
			location = "/1/log/user_report.json"

		# extract details
		if "user_comment" in report:
			user_comment = report["user_comment"]
		else:
			user_comment = ""
		if "error" in report:
			error = report["error"]
		else:
			error = ""
			print("No error passed through")
			return

		try:
			bversion = str(bpy.app.version)
		except:
			bversion = "unknown"

		# Comply with server-side validation, don't exceed lengths
		if len(user_comment) > USER_COMMENT_LENGTH:
			user_comment = user_comment[:USER_COMMENT_LENGTH-1] + "|"
		if len(error) > ERROR_STRING_LENGTH:
			# TODO: make smarter, perhaps grabbing portion of start of error
			# and portion of end to get all needed info
			end_bound = len(error)-ERROR_STRING_LENGTH+1
			error = "|" + error[end_bound:]

		payload = json.dumps({
				"timestamp":{".sv": "timestamp"},
				"version":Tracker.version,
				"blender":bversion,
				"platform":get_platform_details(),
				"error":error,
				"user_comment":user_comment,
				"ID":Tracker.json["install_id"]
			})
		resp = Tracker.request('POST', location, payload, background)

	if Tracker.failsafe is True:
		try:
			runError(background)
		except:
			pass
	else:
		runError(background)


def report_error(function):
	"""Decorator for the execute(self, context) function of operators"""

	def wrapper(self, context):
		try:
			res = function(self, context)
			Tracker._handling_error = False
			return res
		except:
			err = traceback.format_exc()
			print(err) # always print raw traceback
			err = Tracker.remove_indentifiable_information(err)

			# Prevent recusrive popups for errors if operators call other
			# operators, only show the inner-most errors
			if Tracker._handling_error is False:
				Tracker._handling_error = True
				bpy.ops.mcprep.report_error('INVOKE_DEFAULT',error_report=err)

			return {"CANCELLED"}
	return wrapper


def get_platform_details():
	"""OS related information"""
	res = platform.system()+":"+platform.release()
	if len(res) > SHORT_FIELD_MAX:
		res = res[:SHORT_FIELD_MAX-1] + "|"
	return str(res)


# -----------------------------------------------------------------------------
# registration related
# -----------------------------------------------------------------------------


def register(bl_info):
	Tracker.initialize(
		appurl = "https://mcprep-1aa04.firebaseio.com/",
		version = str(bl_info["version"])
		)

	# used to define which server source, not just if's below
	Tracker.dev = conf.dev # True or False

	if Tracker.dev is True:
		Tracker.verbose = True
		Tracker.background = True # test either way
		Tracker.failsafe = False # test either way
		Tracker.tracking_enabled = True # enabled automatically for testing
	else:
		Tracker.verbose = False
		Tracker.background = True
		Tracker.failsafe = True
		Tracker.tracking_enabled = True # User accepted on download

	# try running install
	trackInstalled()


def unregister():
	pass


if __name__ == "__main__":
	register({"bl_info":(2, 99, 0)})
