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

# safe importing, due to rogue python libraries being missing or invalid
# in bad installs cases (if the rest of the addon works, don't make it
# fail to work because of this module)
VALID_IMPORT = True

# critical to at least load these
import os
import bpy

# remaining, wrap in safe-importing
try:
	from . import conf
	from . import util
	import re
	import requests
	import traceback
	import json
	import http.client
	import platform
	import threading
	import textwrap
	import time
	from datetime import datetime
except Exception as err:
	print("[MCPREP Error] Failed tracker module load, invalid import module:")
	print('\t'+err)
	VALID_IMPORT = False


# -----------------------------------------------------------------------------
# global vars
# -----------------------------------------------------------------------------

IDNAME = "mcprep"

# max data/string lengths to match server-side validation,
# if exceeded, request will return denied (no data written)
SHORT_FIELD_MAX = 64-1
USER_COMMENT_LENGTH = 512-1
ERROR_STRING_LENGTH = 1024-1

# -----------------------------------------------------------------------------
# primary class implementation
# -----------------------------------------------------------------------------


class Singleton_tracking(object):

	def __init__(self):
		self._addon = __package__.lower()
		self._appurl = ""
		self._background = False
		self._bg_thread = []
		self._blender_version = ""
		self._dev = False
		self._failsafe = False
		self._handling_error = False
		self._language = ""
		self._platform = ""
		self._port = 443
		self._tracker_idbackup = None
		self._tracker_json = None
		self._tracking_enabled = False
		self._verbose = False
		self._version = ""
		self.json = {}
		self._httpclient_fallback = None # set to True/False after first req
		self._last_request = {} # used to debounce sequential requests
		self._debounce = 3 # seconds to avoid duplicative requests


	# -------------------------------------------------------------------------
	# Getters and setters
	# -------------------------------------------------------------------------

	@property
	def blender_version(self):
		return self._blender_version
	@blender_version.setter
	def blender_version(self, value):
		if value is None:
			self._blender_version = "unknown"
		elif type(value) != type((1,2,3)):
			raise Exception("blender_version must be a tuple")
		else:
			self._blender_version = str(value)

	@property
	def language(self):
		return self._language
	@language.setter
	def language(self, value):
		if value is None:
			self._language = "None"
		elif type(value) != type("string"):
			raise Exception("language must be a string")
		else:
			self._language = self.string_trunc(value)

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

	@property
	def platform(self):
		return self._platform
	@platform.setter
	def platform(self, value):
		if value is None:
			self._platform = "None"
		elif type(value) != type("string"):
			raise Exception("platform must be a string")
		else:
			self._platform = self.string_trunc(value)


	# number/settings for frequency use before ask for enable tracking

	# -------------------------------------------------------------------------
	# Public functions
	# -------------------------------------------------------------------------

	def enable_tracking(self, toggle=True, enable=True):
		if not VALID_IMPORT:
			return
		if toggle:
			self._tracking_enabled = not self._tracking_enabled
		else:
			self._tracking_enabled = enable

		# update static json
		self.json["enable_tracking"] = self._tracking_enabled
		self.save_tracker_json()

	def get_platform_details(self):
		"""Return OS related information."""
		try:
			res = platform.system()+":"+platform.release()
			if len(res) > SHORT_FIELD_MAX:
				res = res[:SHORT_FIELD_MAX-1] + "|"
		except Exception as err:
			print("Error getting platform info: " + str(err))
			return "unknown:unknown"
		return str(res)

	def initialize(self, appurl, version, language=None, blender_version=None):
		"""Load the enable_tracking-preference (in/out), create tracker data."""
		if not VALID_IMPORT:
			return

		self._appurl = appurl
		self._version = version
		self.platform = self.get_platform_details()
		# self.blender_version = blender_version
		self._blender_version = str(blender_version)
		self.language = language

		self._tracker_idbackup = os.path.join(os.path.dirname(__file__),
							os.pardir,self._addon+"_trackerid.json")
		self._tracker_json = os.path.join(os.path.dirname(__file__),
							self._addon+"_tracker.json")

		# create the local file
		# push into BG push update info if true
		# create local cache file locations
		# including search for previous
		self.set_tracker_json()
		return

	def request(self, method, path, payload, background=False, callback=None):
		"""Interface request, either launches on main or a background thread."""
		if not VALID_IMPORT:
			return
		if method not in ["POST", "PUT", "GET"]:
			raise ValueError("Method must be POST, PUT, or GET")
		if background is False:
			return self.raw_request(method, path, payload, callback)
		else:
			# if self._verbose: print("Starting background thread for track call")
			bg_thread = threading.Thread(target=self.raw_request, args=(method, path, payload, callback))
			bg_thread.daemon = True
			#self._bg_threads.append(bg_thread)
			bg_thread.start()
			return "Thread launched"


	def raw_request(self, method, path, payload, callback=None):
		"""Raw connection request, background or foreground.

		To support the widest range of installs, try first using the newer
		requests module, else fall back and keep using http.client
		"""
		if not VALID_IMPORT:
			return

		if self._httpclient_fallback is None:
			# first time run
			resp = None
			try:
				resp = self._raw_request_mod_requests(method, path, payload)
				self._httpclient_fallback = False
			except:
				resp = self._raw_request_mod_http(method, path, payload)
				self._httpclient_fallback = True
		elif self._httpclient_fallback is False:
			resp =  self._raw_request_mod_requests(method, path, payload)
		else:
			resp = self._raw_request_mod_http(method, path, payload)

		if callback is not None:
			if self._verbose:
				print(self._addon+": Running callback")
			callback(resp)
		return resp

	def _raw_request_mod_requests(self, method, path, payload):
		"""Method for connection using the requests library.

		Intentionally raises when errors occur so that fallback method can
		be used. This function works in blender 2.8, and at least 2.79.
		"""
		url = self._appurl + path
		if method=="POST":
			res = requests.post(url, payload)
		elif method=="GET":
			res = requests.get(url)
		elif method=="PUT":
			res = requests.put(url, payload)
		else:
			raise ValueError("raw_request input must be GET, POST, or PUT")

		if not res.ok:
			if self._verbose:
				print("Error occured in requests req: ", str(res.reason))
			raise ValueError("Error occured while requesting data (requests lib)")

		if res.text:
			resp = json.loads(res.text)
		else:
			resp = {}
		if self._verbose:
			if self._dev:
				print(self._addon+" dev response (requests lib): "+str(resp))
			else:
				print(self._addon+" response (requests lib): "+str(resp))
		return resp

	def _raw_request_mod_http(self, method, path, payload):
		"""Method for connection using the http.client library.

		This method functions consistently up until and not including b3d 2.8
		"""

		url = self._appurl.split("//")[1]
		url = url.split("/")[0]
		connection = http.client.HTTPSConnection(url, self._port)
		try:
			connection.connect()
			if self.verbose:
				print(self._addon + ": Connection made to "+str(path))
		except Exception as err:
			print(self._addon + ": Connection failed, intended report destination: "+str(path))
			print("Error: "+str(err))
			return {'status':'NO_CONNECTION'}

		if method=="POST" or method=="PUT":
			connection.request(method, path, payload)
		elif method == "GET":
			connection.request(method, path)
		else:
			raise ValueError("raw_request input must be GET, POST, or PUT")

		raw = connection.getresponse().read()
		resp = json.loads(raw.decode())
		if self._verbose:
			print(self._addon +" response (http lib): "+str(resp))
		return resp

	def set_tracker_json(self):
		if not VALID_IMPORT:
			return
		if self._tracker_json is None:
			raise ValueError("tracker_json is not defined")

		if os.path.isfile(self._tracker_json) is True:
			with open(self._tracker_json) as data_file:
				self.json = json.load(data_file)
				if self._verbose:
					print(self._addon+": Read in json settings from tracker file")
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
					if self._verbose:
						print(self._addon+": Reinstall, getting IDNAME")
					if "IDNAME" in idbackup:
						self.json["install_id"] = idbackup["IDNAME"]
						self.json["status"] = "re-install"
						self.json["install_date"] = idbackup["date"]

			self.save_tracker_json()

		# update any other properties if necessary from json
		self._tracking_enabled = self.json["enable_tracking"]

	def save_tracker_json(self):
		"""Save out current state of the tracker json to file."""
		if not VALID_IMPORT:
			return
		jpath = self._tracker_json
		outf = open(jpath, 'w')
		data_out = json.dumps(self.json, indent=4)
		outf.write(data_out)
		outf.close()
		if self._verbose:
			print(self._addon+": Wrote out json settings to file")

	def save_tracker_idbackup(self):
		"""Save copy of the ID file to parent folder location, for detecting
		reinstalls in the future if the folder is deleted"""
		if not VALID_IMPORT:
			return
		jpath = self._tracker_idbackup

		if "install_id" in self.json and self.json["install_id"] != None:
			outf = open(jpath, 'w')
			idbackup = {"IDNAME":self.json["install_id"],
						"date":self.json["install_date"]}
			data_out = json.dumps(idbackup,indent=4)
			outf.write(data_out)
			outf.close()
			if self._verbose:
				print(self._addon+": Wrote out backup settings to file, with the contents:")
				print(idbackup)

	def remove_indentifiable_information(self, report):
		"""Remove filepath from report logs, which could have included
		sensitive information such as usernames or names"""
		report = report.replace(r'\\', '/').replace(r'\\\\\\', '/')
		if not VALID_IMPORT:
			return report
		try:
			return re.sub(
				# case insensitive match: File "C:/path/.." or File "/path/.."
				r'(?i)File "([a-z]:){0,1}[/\\]{1,2}.*[/\\]{1,2}',
				'File "<addon_path>/',
				str(report))
		except Exception as err:
			print("Error occured while removing info: {}".format(err))
			return "[pii] "+str(report)

	def string_trunc(self, value):
		"""Function which caps max string length."""
		ret = str(value)
		if len(ret)>SHORT_FIELD_MAX:
			ret = ret[:SHORT_FIELD_MAX]
		return ret


# -----------------------------------------------------------------------------
# Create the Singleton instance
# -----------------------------------------------------------------------------


Tracker = Singleton_tracking()


# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------


class TRACK_OT_toggle_enable_tracking(bpy.types.Operator):
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
		if not VALID_IMPORT:
			self.report({"ERROR"}, "Invalid import, all reporting disabled.")
			return {'CANCELLED'}
		if self.tracking == "toggle":
			Tracker.enable_tracking(toggle=True)
		elif self.tracking == "enable":
			Tracker.enable_tracking(toggle=False, enable=True)
		else:
			Tracker.enable_tracking(toggle=False, enable=False)
		return {'FINISHED'}


class TRACK_OT_popup_feedback(bpy.types.Operator):
	bl_idname = IDNAME+".popup_feedback"
	bl_label = "Thanks for using {}!".format(IDNAME)
	bl_description = "Take a survey to give feedback about the addon"
	options = {'REGISTER', 'UNDO'}

	def invoke(self, context, event):
		width = 400 * util.ui_scale()
		return context.window_manager.invoke_props_dialog(self, width=width)

	def draw(self, context):

		self.layout.split()
		col = self.layout.column()
		col.alignment='CENTER'
		col.scale_y = 0.7
		col.label(text="Want to help out even more?")
		col.label(text="Press OK below to open the MCprep survey")
		col.label(text="Responding helps direct development time,")
		col.label(text="and identify those nasty bugs.")
		col.label(text="You help everyone by responding!")

	def execute(self, context):
		bpy.ops.wm.url_open(url="bit.ly/MCprepSurvey")

		return {'FINISHED'}


class TRACK_OT_popup_report_error(bpy.types.Operator):
	bl_idname = IDNAME+".report_error"
	bl_label = "MCprep Error, press OK below to send this report to developers"
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
		width = 500 * util.ui_scale()
		return context.window_manager.invoke_props_dialog(self, width=width)

	def draw_header(self, context):
		self.layout.label(text="", icon="ERROR") # doesn't work/add to draw

	def draw(self, context):
		layout = self.layout

		col = layout.column()
		box = col.box()
		boxcol = box.column()
		boxcol.scale_y = 0.7
		if self.error_report=="":
			box.label(text=" # no error code identified # ")
		else:
			width = 500
			report_lines = self.error_report.split("\n")[:-1]
			tot_ln = 0
			max_ln = 10
			for ln in report_lines:
				sub_lns = textwrap.fill(ln, width-30)
				spl = sub_lns.split("\n")
				for i,s in enumerate(spl):
					boxcol.label(text=s)
					tot_ln+=1
					if tot_ln==max_ln: break
				if tot_ln==max_ln: break
		boxcol.label(text="."*500)
		# boxcol.label(text="System & addon information:")
		sysinfo="Blender version: {}\nMCprep version: {}\nOS: {}\n MCprep install identifier: {}".format(
				Tracker.blender_version,
				Tracker.version,
				Tracker.platform,
				Tracker.json["install_id"],
		)
		for ln in sysinfo.split("\n"):
			boxcol.label(text=ln)

		col.label(text="(Optional) Describe what you were trying to do when the error occured:")
		col.prop(self,"comment",text="")

		row = col.row(align=True)
		split = layout_split(layout, factor=0.6)
		spcol = split.row()
		spcol.label(text="Select 'Send' then press OK to share report")
		split_two = layout_split(split, factor=0.4)
		spcol_two = split_two.row(align=True)
		spcol_two.prop(self,"action",text="")
		spcol_two = split_two.row(align=True)
		p = spcol_two.operator("wm.url_open", text="How is this used?", icon="QUESTION")
		p.url = "https://theduckcow.com/dev/blender/mcprep/reporting-errors/"

	def execute(self, context):
		if not VALID_IMPORT:
			self.report({"ERROR"}, "Invalid import, all reporting disabled.")
			return {'CANCELLED'}

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
	"""Send new install event to database."""
	if not VALID_IMPORT:
		return

	# if already installed, skip
	if Tracker.json["status"] == None and \
			Tracker.json["install_id"] != None: return

	if Tracker.verbose: print(Tracker.addon+" install registered")

	# if no override set, use default
	if background == None:
		background = Tracker.background

	def runInstall(background):

		if Tracker.dev is True:
			location = "/1/track/install_dev.json"
		else:
			location = "/1/track/install.json"

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
				"usertime":Tracker.string_trunc(Tracker.json["install_date"]),
				"version":Tracker.version,
				"blender":Tracker.blender_version,
				"status":Tracker.string_trunc(status),
				"platform":Tracker.platform,
				"language":Tracker.language,
				"ID":str(Tracker.json["install_id"])
			})

		resp = Tracker.request('POST', location, payload, background, callback)

	def callback(arg):
		"""After call, assumes input is dict server response."""
		if type(arg) != type({'name':'ID'}):
			return
		elif "name" not in arg:
			return

		if not Tracker.json["install_id"]:
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


def trackUsage(function, param=None, exporter=None, background=None):
	"""Send usage operator usage + basic metadata to database."""
	if not VALID_IMPORT:
		return
	if Tracker.tracking_enabled is False:
		return # skip if not opted in
	if Tracker.verbose:
		print("{} usage: {}, param: {}, exporter: {}".format(
			Tracker.addon, function, str(param), str(exporter)))

	# if no override set, use default
	if not background:
		background = Tracker.background

	def runUsage(background):

		if Tracker.dev is True:
			location = "/1/track/usage_dev.json"
		else:
			location = "/1/track/usage.json"

		payload = json.dumps({
				"timestamp":{".sv": "timestamp"},
				"version":Tracker.version,
				"blender":Tracker.blender_version,
				"platform":Tracker.platform,
				"function":Tracker.string_trunc(function),
				"param":Tracker.string_trunc(param),
				"exporter":Tracker.string_trunc(exporter),
				"language":Tracker.language,
				"ID":Tracker.json["install_id"]
			})
		resp = Tracker.request('POST', location, payload, background)

	if Tracker.failsafe is True:
		try:
			runUsage(background)
		except:
			pass
	else:
		runUsage(background)


def logError(report, background=None):
	"""Send error report to database."""
	if not VALID_IMPORT:
		return

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
				"blender":Tracker.blender_version,
				"platform":Tracker.platform,
				"error":error,
				"user_comment":user_comment,
				"status":"None",  # used later for flagging if fixed or not
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
	"""Decorator for the execute(self, context) function of operators.

	Both captures any errors for user reporting, and runs the usage tracking
	if/as configured for the operator class. If function returns {'CANCELLED'}
	has no track_function class attribute, or skipUsage==True, then
	usage tracking is skipped.
	"""

	def wrapper(self, context):
		try:
			Tracker._handling_error = False
			res = function(self, context)
			Tracker._handling_error = False
		except:
			err = traceback.format_exc()
			print(err) # always print raw traceback
			err = Tracker.remove_indentifiable_information(err)

			# cut off the first three lines of error, which is this wrapper
			nth_newline = 0
			for ind in range(len(err)):
				if err[ind] in ["\n", "\r"]:
					nth_newline += 1
				if nth_newline == 3:
					if len(err) > ind+1:
						err = err[ind+1:]
					break

			# Prevent recusrive popups for errors if operators call other
			# operators, only show the inner-most errors
			if Tracker._handling_error is False:
				Tracker._handling_error = True
				bpy.ops.mcprep.report_error('INVOKE_DEFAULT', error_report=err)

			return {'CANCELLED'}

		if res=={'CANCELLED'}:
			return res  # cancelled, so skip running usage
		elif hasattr(self, "skipUsage") and self.skipUsage is True:
			# if Tracker.verbose:
			# 	print("Skipping usage")
			return res  # skip running usage

		# Debounc multiple same requests
		run_track = hasattr(self, "track_function") and self.track_function
		if (run_track
			and Tracker._last_request.get("function") == self.track_function
			and Tracker._last_request.get("time") + Tracker._debounce > time.time()
			):
			if Tracker.verbose:
				print("Skipping usage due to debounce")
			run_track = False

		# If successful completion, run analytics function if relevant
		if run_track:
			param = None
			exporter = None
			if hasattr(self, "track_param"):
				param = self.track_param
			if hasattr(self, "track_exporter"):
				exporter = self.track_exporter

			try:
				trackUsage(self.track_function, param=param, exporter=exporter)
			except:
				err = traceback.format_exc()
				print("Error while reporting usage for "+str(self.track_function))
				print(err)
			# always update the last request gone through
			Tracker._last_request = {
				"time": time.time(),
				"function": self.track_function
			}
		return res

	return wrapper


# -----------------------------------------------------------------------------
# registration related
# -----------------------------------------------------------------------------


def layout_split(layout, factor=0.0, align=False):
	"""Intermediate method for pre and post blender 2.8 split UI function"""
	if not hasattr(bpy.app, "version") or bpy.app.version < (2, 80):
		return layout.split(percentage=factor, align=align)
	return layout.split(factor=factor, align=align)


def make_annotations(cls):
	"""Add annotation attribute to class fields to avoid Blender 2.8 warnings"""
	if not hasattr(bpy.app, "version") or bpy.app.version < (2, 80):
		return cls
	bl_props = {k: v for k, v in cls.__dict__.items() if isinstance(v, tuple)}
	if bl_props:
		if '__annotations__' not in cls.__dict__:
			setattr(cls, '__annotations__', {})
		annotations = cls.__dict__['__annotations__']
		for k, v in bl_props.items():
			annotations[k] = v
			delattr(cls, k)
	return cls


classes = (
	TRACK_OT_toggle_enable_tracking,
	TRACK_OT_popup_feedback,
	TRACK_OT_popup_report_error
)


def register(bl_info):
	"""Setup the tracker and register install."""
	global VALID_IMPORT

	bversion = None
	# for compatibility to prior blender (2.75?)
	try:
		bversion = bpy.app.version
	except Exception as err:
		err = traceback.format_exc()
		print("Could not get blender version:")
		print(err)

	language = None
	if hasattr(bpy.app, "version") and bpy.app.version >= (2, 80):
		if hasattr(bpy.context, "preferences"):
			system = bpy.context.preferences.view
		elif hasattr(bpy.context, "user_preferences"):
			system = bpy.context.user_preferences.view
		else:
			system = None
		if system and system.use_international_fonts:
			language = system.language
	else:
		system = bpy.context.user_preferences.system
		if system.use_international_fonts:
			language = system.language

	try:
		Tracker.initialize(
			appurl = "https://mcprep-1aa04.firebaseio.com/",
			version = str(bl_info["version"]),
			language = language,
			blender_version = bversion)
	except Exception as err:
		err = traceback.format_exc()
		print(err)
		VALID_IMPORT = False

	# used to define which server source, not just if's below
	if VALID_IMPORT:
		Tracker.dev = conf.dev # True or False
	else:
		Tracker.dev = False

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

	for cls in classes:
		make_annotations(cls)
		bpy.utils.register_class(cls)

	# register install
	trackInstalled()


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)


if __name__ == "__main__":
	register({"bl_info":(2, 99, 0)})
