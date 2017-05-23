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

# -----------------------------------------------------------------------------
# Structure plan
# -----------------------------------------------------------------------------

"""
Key funcitonality:
- Send notice when first installing the addon and enabling (first time only)
-- (Try to get unique identifier to prevent doubling?)
x Track when functions are used
-- Track how often used, just keep local number/count usage
-- keep unique ID for user... could scramble timestamp first installed+userpath?
-- could do sneaky parsing of other blender folders to see if addon found & has pre-existing ID
-- (relative only pathing ofc)
xx Try to send in background when using
-- and if failed save to file & set flag to try again later
- Feedback form?? >> direct emails to support@theduckcow.com could do
- Consideirng both google analytics pinging as well as DB pushes? one or the other
- when asking to enable tracking, second popup to say hey, advanced too?
-- open advanced settings, fields for more details/could also be in that conditional popup
- Request for feedback? popup also after some interval if not used?

Things to track/push
- when installed (by default, agreed to on download)
- FORCE them to agree to terms of use in addon panel before doing anything???
(personal thing/specific to this addon)
- track date.. different from submission timestamp potentially
- addon version
- additional tracking (optional):
-- blender version
xx OS running
-- optional profiler info? e.g. tick your age range, # eyars experince w/ blender, etc


"""


"""data testing dump

curl -X POST -d '{"timestamp":0,"version":"v2.9.9","blender":"2.77","status":"New install"}' 'https://mcprep-1aa04.firebaseio.com/1/track/install_dev.json'

curl -X GET 'https://mcprep-1aa04.firebaseio.com/1/SECRET.json'

"""

import os
import json
import http.client
import platform
import threading
import bpy
from datetime import datetime

from . import conf


# -----------------------------------------------------------------------------
# global vars
# -----------------------------------------------------------------------------


idname = "mcprep"


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




	# number/settings for frequency use before ask for enable tracking

	# 

	# -------------------------------------------------------------------------
	# Public functions
	# -------------------------------------------------------------------------

	def enable_tracking(self, toggle=True, enable=True):
		# respect toggle primarily
		if toggle == True:
			self._tracking_enabled = not self._tracking_enabled
		else:
			self._tracking_enabled = enable

		# update static json
		self.json["enable_tracking"] = self._tracking_enabled
		self.save_tracker_json()	

	def initialize(self, appurl, version):

		self._appurl = appurl
		self._version = version
		# load the enable_tracking-preference (ie in or out)

		# load or create the tracker data
		self.set_tracker_json()

		return

		# create the local file
		# push into BG push update info if true
		# create local cache file locations
		# including search for previous

	# interface request, either launches on main or background
	def request(self, method, path, payload, background=False, callback=None):
		if method not in ["POST","PUT","GET"]:
			raise ValueError("Method must be POST, PUT, or GET")


		if background==False:
			return self.raw_request(method, path, payload, callback)
			
		else:
			# launch the daemon

			# if self._async_checking == True:
			# 	return
			if self._verbose: print("Starting background thread")
			bg_thread = threading.Thread(target=self.raw_request, args=(method, path, payload, callback))
			bg_thread.daemon = True
			#self._bg_threads.append(bg_thread)
			bg_thread.start()

			return "Thread launched"

	# raw request, may be in background thread or main
	def raw_request(self, method, path, payload, callback=None):
		# convert url into domain
		url = self._appurl.split("//")[1]
		url = url.split("/")[0]

		connection = http.client.HTTPSConnection(url, self._port)
		try:
			connection.connect()
			if self.verbose:print("Connection made to "+str(path))
		except:
			print("Connection not made, verify connectivity; intended: "+str(path))
			return {'status':'NO_CONNECTION'}

		if method=="POST" or method=="PUT":
			connection.request(method, path, payload)
		elif method == "GET": # GET
			connection.request(method, path)
		else:
			raise ValueError("raw_request input must be GET, POST, or PUT")

		raw = connection.getresponse().read()
		resp = json.loads( raw.decode() )
		if self._verbose:print("Response: "+str(resp))	

		if callback != None:
			if self._verbose:print("Running callback")
			callback(resp)

		return resp



	def set_tracker_json(self):
		if self._tracker_json == None:
			raise ValueError("tracker_json is not defined")

		if os.path.isfile(self._tracker_json)==True:
			with open(self._tracker_json) as data_file:
				self.json = json.load(data_file)
				if self._verbose:print("Read in json settings from tracker file")
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
					if self._verbose:print("Reinstall, getting idname")
					if "idname" in idbackup:
						self.json["install_id"] = idbackup["idname"]
						self.json["status"] = "re-install"
						self.json["install_date"] = idbackup["date"]

			self.save_tracker_json()

		# update any other properties if necessary from json
		self._tracking_enabled = self.json["enable_tracking"]


	def save_tracker_json(self):

		jpath = self._tracker_json
		outf = open(jpath,'w')
		data_out = json.dumps(self.json,indent=4)
		outf.write(data_out)
		outf.close()
		if self._verbose:
			print("Wrote out json settings to file, with the contents:")
			print(self.json)

	def save_tracker_idbackup(self):

		jpath = self._tracker_idbackup
		
		if "install_id" in self.json and self.json["install_id"] != None:
			outf = open(jpath,'w')
			idbackup = {"idname":self.json["install_id"], 
						"date":self.json["install_date"]}
			data_out = json.dumps(idbackup,indent=4)
			outf.write(data_out)
			outf.close()
			if self._verbose:
				print("Wrote out backup settings to file, with the contents:")
				print(idbackup)


	# def tracking(set='disable'):

	# def checkenable_tracking(): # ie has initial install check been done?
	# ^ similar as above, maybe unnecessary

	# def usageStat(function): # actually run push; function is key for what was ran/what to record
		# allow more complex info?



# -----------------------------------------------------------------------------
# Create the Singleton instance
# -----------------------------------------------------------------------------



Tracker = Singleton_tracking()



# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------



class toggleenable_tracking(bpy.types.Operator):
	"""Toggle anonymous usage tracking to help the developers, disabled by default. The only data tracked is what functions are used, and the timestamp of the addon installation"""
	bl_idname = idname+".toggle_enable_tracking"
	bl_label = "Toggle opt-in for analytics tracking"
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
	bl_idname = idname+".popup_feedback"
	bl_label = "Thanks for using {}!".format(idname)
	options = {'REGISTER', 'UNDO'}

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self, width=400)

	def draw(self, context):

		# seems that only the first url open works here,
		# so many need to create operators that are just url open operations
		# for the other in-popup items.

		row = self.layout.row()
		self.layout.split()
		row = self.layout.row()
		row.label("See the latest")
		p = row.operator("wm.url_open","on the website")
		p.url = "http://theduckcow.com/dev/blender/mcprep/"

		row = self.layout.row()
		row.label("Want to support development?")
		p = row.operator("wm.url_open","Consider donating")
		p.url = "bit.ly/donate2TheDuckCow"

		self.layout.split()
		col = self.layout.column()
		col.alignment='CENTER'
		col.label("PRESS OKAY TO OPEN SURVEY BELOW")
		self.layout.split()
		col = self.layout.column()
		col.scale_y = 0.7
		col.label("Responding to the survey helps drive what devleopment is worked on")
		col.label("and identify those nasty bugs. You help everyone by responding!")

	def execute(self, context):
		bpy.ops.wm.url_open(url="bit.ly/MCprepSurvey")

		return {'FINISHED'}


# -----------------------------------------------------------------------------
# additional functions
# -----------------------------------------------------------------------------


def trackInstalled(background=None):
	# if already installed, skip
	if Tracker.json["status"] == None and \
			Tracker.json["install_id"] != None: return

	if Tracker.verbose: print("Tracking install")

	# if no override set, use default
	if background == None:
		background = Tracker.background

	def runInstall(background):


		if Tracker.dev==True:
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
				"platform":platform.system()+":"+platform.release()
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


	if Tracker.failsafe == True:
		try:
			runInstall(background)
		except:
			pass
	else:
		runInstall(background)


def trackUsage(function, param=None, background=None):
	if Tracker.tracking_enabled == False: return # skip if not opted in
	if conf.internal_change == True: return # skip if internal run

	if Tracker.verbose: print("Tracking usage: "+function +", param: "+str(param))

	# if no override set, use default
	if background == None:
		background = Tracker.background

	def runUsage(background):

		if Tracker.dev==True:
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
				"platform":platform.system()+":"+platform.release(),
				"function":function,
				"param":str(param),
				"ID":Tracker.json["install_id"]
			})

		resp = Tracker.request('POST', location, payload, background)

	if Tracker.failsafe == True:
		try:
			runUsage(background)
		except:
			pass
	else:
		runUsage(background)


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

	if Tracker.dev == True:
		Tracker.verbose = False
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
	register({"bl_info":(2,99,0)})

