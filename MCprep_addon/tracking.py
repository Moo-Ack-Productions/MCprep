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

# critical to at least load these
import os
import bpy


# safe importing, due to rogue python libraries being missing or invalid
# in bad installs cases (if the rest of the addon works, don't make it
# fail to work because of this module)
VALID_IMPORT = True

# Request timeout (total request time may still be longer)
TIMEOUT = 60

# Ids with known analytical problems, such as clobbered-together installs.
# If we see any of these IDs in local json files, still treat as a re-install
# but replace the ID with the new one received.
SKIP_IDS = ["-Nb8TgbvAoxHrnEe1WFy"]


# remaining, wrap in safe-importing
try:
	from . import util
	from .addon_updater import Updater as updater
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
	from .conf import env
except Exception as err:
	print("[MCPREP Error] Failed tracker module load, invalid import module:")
	print(f"\t{err}")
	VALID_IMPORT = False


# -----------------------------------------------------------------------------
# global vars
# -----------------------------------------------------------------------------

IDNAME = "mcprep"

# max data/string lengths to match server-side validation,
# if exceeded, request will return denied (no data written)
SHORT_FIELD_MAX = 64 - 1
USER_COMMENT_LENGTH = 512 - 1
ERROR_STRING_LENGTH = 1024 - 1


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
		self._httpclient_fallback = None  # set to True/False after first req
		self._last_request = {}  # used to debounce sequential requests
		self._debounce = 5  # seconds to avoid duplicative requests
		self._feature_set = 0  # Supported addon features (e.g. experimental)

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
		elif not isinstance(value, tuple):
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
		elif not isinstance(value, str):
			raise Exception(f"language must be a string: {value}, {type(value)}")
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
		except Exception as e:
			raise ValueError("Verbose must be a boolean value") from e

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
		except Exception as e:
			raise ValueError("failsafe must be a boolean value") from e

	@property
	def dev(self):
		return self._dev

	@dev.setter
	def dev(self, value):
		try:
			self._dev = bool(value)
		except Exception as e:
			raise ValueError("background must be a boolean value") from e

	@property
	def background(self):
		return self._background

	@background.setter
	def background(self, value):
		try:
			self._background = bool(value)
		except Exception as e:
			raise ValueError("background must be a boolean value") from e

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
		elif not isinstance(value, str):
			raise Exception("platform must be a string")
		else:
			self._platform = self.string_trunc(value)

	@property
	def feature_set(self):
		values = ["", "supported", "experimental"]
		return values[self._feature_set]

	@feature_set.setter
	def feature_set(self, value):
		if not value:
			self._feature_set = 0
		elif value == "supported":
			self._feature_set = 1
		elif value == "experimental":
			self._feature_set = 2
		else:
			raise ValueError(
				"feature_set must be one of supported, experimental, or None")

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
			res = f"{platform.system()}:{platform.release()}"
			if len(res) > SHORT_FIELD_MAX:
				res = res[:SHORT_FIELD_MAX - 1] + "|"
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

		self._tracker_idbackup = os.path.join(
			os.path.dirname(__file__),
			os.pardir,
			self._addon + "_trackerid.json")
		self._tracker_json = os.path.join(
			os.path.dirname(__file__),
			self._addon + "_tracker.json")

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
			bg_thread = threading.Thread(
				target=self.raw_request, args=(method, path, payload, callback))
			bg_thread.daemon = True
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
			except Exception:
				resp = self._raw_request_mod_http(method, path, payload)
				self._httpclient_fallback = True
		elif self._httpclient_fallback is False:
			resp = self._raw_request_mod_requests(method, path, payload)
		else:
			resp = self._raw_request_mod_http(method, path, payload)

		if callback is not None:
			if self._verbose:
				print(self._addon + ": Running callback")
			callback(resp)
		return resp

	def _raw_request_mod_requests(self, method, path, payload):
		"""Method for connection using the requests library.

		Intentionally raises when errors occur so that fallback method can
		be used. This function works in blender 2.8, and at least 2.79.
		"""
		url = self._appurl + path
		if method == "POST":
			res = requests.post(url, payload, timeout=TIMEOUT)
		elif method == "GET":
			res = requests.get(url, timeout=TIMEOUT)
		elif method == "PUT":
			res = requests.put(url, payload, timeout=TIMEOUT)
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
			print("{} {} response (requests lib) {} at {}".format(
				self._addon, "dev" if self._dev else "", resp, path))
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
				print(f"{self._addon}: Connection made to {path}")
		except Exception as err:
			print(f"{self._addon}: Connection failed to: {path}")
			print(f"Error: {err}")
			return {'status': 'NO_CONNECTION'}

		if method in ("POST", "PUT"):
			connection.request(method, path, payload)
		elif method == "GET":
			connection.request(method, path)
		else:
			raise ValueError("raw_request input must be GET, POST, or PUT")

		raw = connection.getresponse().read()
		resp = json.loads(raw.decode())
		if self._verbose:
			print("{} {} response (http lib) {} at {}".format(
				self._addon, "dev" if self._dev else "", resp, path))
		return resp

	def set_tracker_json(self):
		if not VALID_IMPORT:
			return
		if self._tracker_json is None:
			raise ValueError("tracker_json is not defined")

		# Placeholder struc before saving to class
		_json = {
			"install_date": None,
			"install_id": None,
			"enable_tracking": False,
			"status": None,
			"metadata": {}
		}

		valid_tracker = False
		if os.path.isfile(self._tracker_json) is True:
			with open(self._tracker_json) as data_file:
				jdata = json.load(data_file)

			_json = jdata
			if self._verbose:
				print(f"{self._addon}: Read in json settings from tracker file")
			if jdata.get("install_id") in SKIP_IDS:
				valid_tracker = False
				_json["install_id"] = None
				_json["status"] = "invalid_id"
				if self._verbose:
					print(f"{self._addon}: Skip ID detected, treat as new")
			else:
				valid_tracker = True

		if os.path.isfile(self._tracker_idbackup):
			with open(self._tracker_idbackup) as data_file:
				idbackup = json.load(data_file)

			bu_id = idbackup.get("IDNAME")
			if bu_id in SKIP_IDS:
				if self._verbose:
					print(f"{self._addon}: Skipping blocked ID list")

				if valid_tracker is True:
					# If the backup id is bad, but the local id is good, just
					# re-use the child (and immediately re-create backup).
					_json["install_date"] = idbackup["date"]
					os.remove(self._tracker_idbackup)  # Will be re-generated.
					self.json = _json
					Tracker.save_tracker_idbackup()
				else:
					# Still count as a reinstall
					_json["status"] = "re-install"
					_json["install_date"] = idbackup["date"]

			elif not valid_tracker and bu_id is not None:
				if self._verbose:
					print(f"{self._addon}: Reinstall, getting IDNAME")
				_json["install_id"] = idbackup["IDNAME"]
				_json["status"] = "re-install"
				_json["install_date"] = idbackup["date"]

			self.json = _json
			self.save_tracker_json()
		else:
			# Tracker was valid, so just load it.
			self.json = _json

		# Update any other properties if necessary from json
		self._tracking_enabled = self.json.get("enable_tracking", False)

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
			print(f"{self._addon}: Wrote out json settings to file")

	def save_tracker_idbackup(self):
		"""Save copy of the ID file to parent folder location, for detecting
		reinstalls in the future if the folder is deleted"""
		if not VALID_IMPORT:
			return
		jpath = self._tracker_idbackup

		if "install_id" in self.json and self.json["install_id"] is not None:
			outf = open(jpath, 'w')
			idbackup = {
				"IDNAME": self.json["install_id"],
				"date": self.json["install_date"]}
			data_out = json.dumps(idbackup, indent=4)
			outf.write(data_out)
			outf.close()
			if self._verbose:
				print(
					f"{self._addon}: Wrote out backup settings to file, with the contents:")
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
			return f"[pii] {report}"

	def string_trunc(self, value):
		"""Function which caps max string length."""
		ret = str(value)
		if len(ret) > SHORT_FIELD_MAX:
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
	bl_idname = f"{IDNAME}.toggle_enable_tracking"
	bl_label = "Toggle opt-in for analytics tracking"
	bl_description = (
		"Toggle anonymous usage tracking to help the developers. "
		"The only data tracked is what MCprep functions are used, key blender"
		"/addon information, and the timestamp of the addon installation")
	options = {'REGISTER', 'UNDO'}

	tracking: bpy.props.EnumProperty(
		items=[
			('toggle', 'Toggle', 'Toggle operator use tracking'),
			('enable', 'Enable', 'Enable operator use tracking'),
			('disable', 'Disable', 'Disable operator use tracking (if already on)')],
		name="tracking")

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
	bl_idname = f"{IDNAME}.popup_feedback"
	bl_label = f"Thanks for using {IDNAME}!"
	bl_description = "Take a survey to give feedback about the addon"
	options = {'REGISTER', 'UNDO'}

	def invoke(self, context, event):
		width = 400 * util.ui_scale()
		return context.window_manager.invoke_props_dialog(self, width=width)

	def draw(self, context):

		self.layout.split()
		col = self.layout.column()
		col.alignment = 'CENTER'
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
	bl_idname = f"{IDNAME}.report_error"
	bl_label = "MCprep Error, press OK below to send this report to developers"
	bl_description = "Report error to database, add additional comments for context"

	error_report: bpy.props.StringProperty(default="")
	comment: bpy.props.StringProperty(
		default="",
		maxlen=USER_COMMENT_LENGTH,
		options={'SKIP_SAVE'})

	action: bpy.props.EnumProperty(
		items=[
			('report', 'Send', 'Send the error report to developers, fully anonymous'),
			('ignore', "Don't send", "Ignore this error report")],
	)

	def invoke(self, context, event):
		width = 500 * util.ui_scale()
		return context.window_manager.invoke_props_dialog(self, width=width)

	def draw_header(self, context):
		self.layout.label(text="", icon="ERROR")  # doesn't work/add to draw

	def draw(self, context):
		layout = self.layout

		col = layout.column()
		box = col.box()
		boxcol = box.column()
		boxcol.scale_y = 0.7
		if self.error_report == "":
			box.label(text=" # no error code identified # ")
		else:
			width = 500
			report_lines = self.error_report.split("\n")[:-1]
			tot_ln = 0
			max_ln = 10
			for ln in report_lines:
				sub_lns = textwrap.fill(ln, width - 30)
				spl = sub_lns.split("\n")
				for i, s in enumerate(spl):
					boxcol.label(text=s)
					tot_ln += 1
					if tot_ln == max_ln:
						break
				if tot_ln == max_ln:
					break
		boxcol.label(text="." * 500)
		# boxcol.label(text="System & addon information:")
		sysinfo = (
			f"Blender version: {Tracker.blender_version}\n"
			f"MCprep version: {Tracker.version}\n"
			f"OS: {Tracker.platform}\n"
			f"MCprep install identifier: {Tracker.json['install_id']}")
		for ln in sysinfo.split("\n"):
			boxcol.label(text=ln)

		col.label(text="(Optional) Describe what you were trying to do when the error occured:")
		col.prop(self, "comment", text="")

		row = col.row(align=True)
		split = layout_split(layout, factor=0.6)
		spcol = split.row()
		spcol.label(text="Select 'Send' then press OK to share report")
		split_two = layout_split(split, factor=0.4)
		spcol_two = split_two.row(align=True)
		spcol_two.prop(self, "action", text="")
		spcol_two = split_two.row(align=True)
		p = spcol_two.operator(
			"wm.url_open", text="How is this used?", icon="QUESTION")
		p.url = "https://theduckcow.com/dev/blender/mcprep/reporting-errors/"

	def execute(self, context):
		# if in headless mode, skip
		if bpy.app.background:
			env.log("Skip Report logging, running headless")
			env.log("Would have reported:")
			raise RuntimeError(self.error_report)
			return {'CANCELLED'}

		if not VALID_IMPORT:
			self.report({"ERROR"}, "Invalid import, all reporting disabled.")
			return {'CANCELLED'}

		if self.action == "ignore":
			return {"FINISHED"}
		# also do followup callback for hey, check here for issues or support?
		report = {"error": self.error_report, "user_comment": self.comment}
		if self.action == 'report':
			res = logError(report)
			if Tracker.verbose:
				print("Logged user report, with server response:")
				print(res)
			self.report({"INFO"}, "Thanks for sharing the report")

		return {'FINISHED'}


# -----------------------------------------------------------------------------
# additional functions
# -----------------------------------------------------------------------------


def trackInstalled(background=None):
	"""Send new install event to database."""
	if not VALID_IMPORT:
		return

	# if already installed, skip
	if not Tracker.json.get("status") and Tracker.json.get("install_id"):
		return

	if Tracker.verbose:
		print(Tracker.addon + " install registered")

	# if no override set, use default
	if background is None:
		background = Tracker.background

	def runInstall(background):

		if Tracker.dev is True:
			location = "/1/track/install_dev.json"
		else:
			location = "/1/track/install.json"

		# capture re-installs/other status events
		if Tracker.json.get("status") is None:
			status = "New install"
		else:
			status = Tracker.json["status"]
			Tracker.json["status"] = None
			Tracker.save_tracker_json()

		Tracker.json["install_date"] = str(datetime.now())
		payload = json.dumps({
			"timestamp": {".sv": "timestamp"},
			"usertime": Tracker.string_trunc(Tracker.json["install_date"]),
			"version": Tracker.version,
			"blender": Tracker.blender_version,
			"status": Tracker.string_trunc(status),
			"platform": Tracker.platform,
			"language": Tracker.language,
			"ID": str(Tracker.json.get("install_id", ""))
		})

		_ = Tracker.request('POST', location, payload, background, callback)

	def callback(arg):
		"""After call, assumes input is dict server response."""
		if not isinstance(arg, dict):
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
		except Exception:
			pass
	else:
		runInstall(background)


def trackUsage(function, param=None, exporter=None, background=None):
	"""Send usage operator usage + basic metadata to database."""
	if not VALID_IMPORT:
		return
	if Tracker.tracking_enabled is False:
		return  # skip if not opted in
	if Tracker.verbose:
		print("{} usage: {}, param: {}, exporter: {}, mode: {}".format(
			Tracker.addon, function, param, exporter, Tracker.feature_set))

	# if no override set, use default
	if background is None:
		background = Tracker.background

	def runUsage(background):

		if Tracker.dev is True:
			location = "/1/track/usage_dev.json"
		else:
			location = "/1/track/usage.json"

		payload = json.dumps({
			"timestamp": {".sv": "timestamp"},
			"version": Tracker.version,
			"blender": Tracker.blender_version,
			"platform": Tracker.platform,
			"function": Tracker.string_trunc(function),
			"param": Tracker.string_trunc(param),
			"exporter": Tracker.string_trunc(exporter),
			"language": Tracker.language,
			"ID": Tracker.json["install_id"],
			"mode": Tracker._feature_set
		})
		_ = Tracker.request('POST', location, payload, background)

	if Tracker.failsafe is True:
		try:
			runUsage(background)
		except Exception:
			pass
	else:
		runUsage(background)


def logError(report: dict, background=None):
	"""Send error report to database.

	report: structure like {"error": str, "user_comment": str}
	"""
	if not VALID_IMPORT:
		return

	# if no override set, use default
	if background is None:
		background = Tracker.background

	def runError(background):
		# ie auto sent in background, must adhere to tracking usage
		if Tracker.tracking_enabled is False:
			return  # skip if not opted in

		if Tracker.dev is True:
			location = "/1/log/user_report_dev.json"
		else:
			location = "/1/log/user_report.json"

		# Extract details
		user_comment = report.get("user_comment", "")
		error = report.get("error", None)
		if error is None:
			print("No error passed through")
			return

		# Comply with server-side validation, don't exceed lengths
		if len(user_comment) > USER_COMMENT_LENGTH:
			user_comment = user_comment[:USER_COMMENT_LENGTH - 1] + "|"
		if len(error) > ERROR_STRING_LENGTH:
			# TODO: make smarter, perhaps grabbing portion of start of error
			# and portion of end to get all needed info
			end_bound = len(error) - ERROR_STRING_LENGTH + 1
			error = "|" + error[end_bound:]

		payload = json.dumps({
			"timestamp": {".sv": "timestamp"},
			"version": Tracker.version,
			"blender": Tracker.blender_version,
			"platform": Tracker.platform,
			"error": error,
			"user_comment": user_comment,
			"status": "None",  # used later for flagging if fixed or not
			"ID": Tracker.json["install_id"],
			"mode": Tracker._feature_set
		})
		_ = Tracker.request('POST', location, payload, background)

	if Tracker.failsafe is True:
		try:
			runError(background)
		except Exception:
			pass
	else:
		runError(background)


def report_error(function):
	"""Decorator for the execute(self, context) function of operators.

	Both captures any errors for user reporting, and runs the usage tracking
	if/as configured for the operator class. If function returns {'CANCELLED'},
	has no track_function class attribute, or skipUsage==True, then
	usage tracking is skipped.
	"""

	def wrapper(self, context):
		try:
			Tracker._handling_error = False
			res = function(self, context)
			Tracker._handling_error = False
		except Exception:
			err = traceback.format_exc()
			print(err)  # Always print raw traceback.

			if updater.json.get("just_updated") is True:
				print("MCprep was just updated, try restarting blender.")
				self.report(
					{"ERROR"},
					"An error occurred - TRY RESTARTING BLENDER since MCprep just updated")
				return {'CANCELLED'}

			err = Tracker.remove_indentifiable_information(err)

			# cut off the first three lines of error, which is this wrapper
			nth_newline = 0
			for ind in range(len(err)):
				if err[ind] in ["\n", "\r"]:
					nth_newline += 1
				if nth_newline == 3:
					if len(err) > ind + 1:
						err = err[ind + 1:]
					break

			# Prevent recusrive popups for errors if operators call other
			# operators, only show the inner-most errors
			if Tracker._handling_error is False:
				Tracker._handling_error = True
				bpy.ops.mcprep.report_error('INVOKE_DEFAULT', error_report=err)
			return {'CANCELLED'}

		if res == {'CANCELLED'}:
			return res  # cancelled, so skip running usage
		elif hasattr(self, "skipUsage") and self.skipUsage is True:
			return res  # skip running usage
		elif VALID_IMPORT is False:
			env.log("Skipping usage, VALID_IMPORT is False")
			return

		try:
			wrapper_safe_handler(self)
		except Exception:
			err = traceback.format_exc()
			print(f"Error while reporting usage for {self.track_function}")
			print(err)

		return res

	def wrapper_safe_handler(self):
		"""Safely report usage, while debouncing multiple of requests.

		Wrapped at this level as time module could have failed to import, used
		during the run check
		"""
		run_track = hasattr(self, "track_function") and self.track_function
		if (run_track
			and Tracker._last_request.get("function") == self.track_function
			and Tracker._last_request.get("time") + Tracker._debounce > time.time()
			):
			env.log("Skipping usage due to debounce")
			run_track = False

		# If successful completion, run analytics function if relevant
		if bpy.app.background and run_track:
			env.log("Background mode, would have tracked usage: " + self.track_function)
		elif run_track:
			param = None
			exporter = None
			if hasattr(self, "track_param"):
				param = self.track_param
			if hasattr(self, "track_exporter"):
				exporter = self.track_exporter

			try:
				trackUsage(self.track_function, param=param, exporter=exporter)
			except Exception:
				err = traceback.format_exc()
				print(f"Error while reporting usage for {self.track_function}")
				print(err)

			# always update the last request gone through
			Tracker._last_request = {
				"time": time.time(),
				"function": self.track_function
			}

	return wrapper


# -----------------------------------------------------------------------------
# registration related
# -----------------------------------------------------------------------------


def layout_split(layout, factor=0.0, align=False):
	"""Intermediate method for pre and post blender 2.8 split UI function"""
	return layout.split(factor=factor, align=align)


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

		if not system:
			pass
		elif hasattr(system, "language"):
			language = system.language
	else:
		system = bpy.context.user_preferences.system
		if system.use_international_fonts:
			language = system.language

	try:
		Tracker.initialize(
			appurl="https://mcprep-1aa04.firebaseio.com/",
			version=str(bl_info["version"]),
			language=language,
			blender_version=bversion)
	except Exception as err:
		err = traceback.format_exc()
		print(err)
		VALID_IMPORT = False

	# used to define which server source, not just if's below
	if VALID_IMPORT:
		Tracker.dev = env.dev_build  # True or False
	else:
		Tracker.dev = False

	if Tracker.dev is True:
		Tracker.verbose = True
		Tracker.background = True  # test either way
		Tracker.failsafe = False  # test either way
		Tracker.tracking_enabled = True  # enabled automatically for testing
	else:
		Tracker.verbose = False
		Tracker.background = True
		Tracker.failsafe = True
		Tracker.tracking_enabled = True  # User accepted on download

	for cls in classes:
		bpy.utils.register_class(cls)

	# register install
	trackInstalled()


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
