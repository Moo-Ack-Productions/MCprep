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

"""
This code is open source under the MIT license.
Its purpose is to increase the workflow of creating Minecraft
related renders and animations, by automating certain tasks.

Developed and tested for blender 2.72 up to the indicated blender version below

The addon must be installed as a ZIP folder, not an individual python script.

Source code available on github as well as more information:
https://github.com/TheDuckCow/MCprep.git

"""

########
# Analytics functions
def install():
	vr = ver
	try:
		pydir = bpy.path.abspath(os.path.dirname(__file__))
		if os.path.isfile(pydir+"/optin") or os.path.isfile(pydir+"/optout"):
			# this means it has already installed once, don't count as another
			return
		else:
			f = open(pydir+"/optout", 'w') # make new file, empty
			f.close()
		import urllib.request
		d = urllib.request.urlopen("http://www.theduckcow.com/data/mcprepinstall.html",timeout=10).read().decode('utf-8')
		ks = d.split("<br>")
		ak = ks[1]
		rk = ks[2]
		import json,http.client
		connection = http.client.HTTPSConnection('api.parse.com', 443)
		connection.connect()
		d = ''
		if v:d="_dev"
		if v:vr+=' dev'
		connection.request('POST', '/1/classes/install'+d, json.dumps({
			   "version": vr,
			 }), {
				"X-Parse-Application-Id": ak,
				"X-Parse-REST-API-Key": rk,
				"Content-Type": "application/json"
			 })
		result = json.loads(   (connection.getresponse().read()).decode())
	except:
		# if v:print("Register connection failed/timed out")
		return

def usageStat(function):
	vr = ver
	if v:vr+=' dev'
	if v:print("Running USAGE STATS for: {x}".format(x=function))
	
	try:
		count = -1
		# first grab/increment the text file's count
		pydir = bpy.path.abspath(os.path.dirname(__file__))
		if os.path.isfile(pydir+"/optin"):
			f = open(pydir+"/optin", 'r')
			ln = f.read()
			f.close()
			# fcns = ln.split('\n')
			# for entry in fcns:
			if function in ln:
				if v:print("found function, checking num")
				i0 = ln.index(function)
				i = i0+len(function)+1
				start = ln[:i]
				if '\n' in ln[i:]:
					if v:print("not end of file")
					i2 = ln[i:].index('\n') # -1 or not?
					if v:print("pre count++:"+ln[i:][:i2]+",{a} {b}".format(a=i,b=i2))
					count = int(ln[i:][:i2])+1
					if v:print("fnct count: "+str(count))
					ln = start+str(count)+ln[i:][i2:]
				else:
					if v:print("end of file adding")
					count = int(ln[i:])+1
					if v:print("fnt count: "+str(count))
					ln = start+str(count)+'\n'
				f = open(pydir+"/optin", 'w')
				f.write(ln)
				f.close()
			else:
				if v:print("adding function")
				count = 1
				ln+="{x}:1\n".format(x=function)
				f = open(pydir+"/optin", 'w')
				f.write(ln)
				f.close()


		import urllib.request

		d = urllib.request.urlopen("http://www.theduckcow.com/data/mcprepinstall.html",timeout=10).read().decode('utf-8')
		ks = d.split("<br>")
		ak = ks[1]
		rk = ks[2]
		import json,http.client
		connection = http.client.HTTPSConnection('api.parse.com', 443)
		connection.connect()
		d = ''
		if v:d="_dev"
		connection.request('POST', '/1/classes/usage'+d, json.dumps({
			   "function": function,
			   "version":vr,
			   "count": count, # -1 for not implemented yet/error
			 }), {
				"X-Parse-Application-Id": ak,
				"X-Parse-REST-API-Key": rk,
				"Content-Type": "application/json"
			 })
		result = json.loads(   (connection.getresponse().read()).decode())
		if v:print("Sent usage stat, returned: {x}".format(x=result))
	except:
		if v:print("Failed to send stat")
		return

def checkOptin():
	pydir = bpy.path.abspath(os.path.dirname(__file__))
	if os.path.isfile(pydir+"/optin"):
		return True
	else:
		return False

def tracking(set='disable'):
	if v:print("Setting the tracking file:")
	try:
		pydir = bpy.path.abspath(os.path.dirname(__file__))
		# print("pydir: {x}".format(x = pydir))

		if set=='disable' or set==False:
			if os.path.isfile(pydir+"/optout"):
				# print("already optout")
				return # already disabled
			elif os.path.isfile(pydir+"/optin"):
				os.rename(pydir+"/optin",pydir+"/optout")
				# print("renamed optin to optout")
			else:
				# f = open(pydir+"/optout.txt", 'w') # make new file, empty
				# f.close()
				# print("Created new opt-out file")
				# DON'T create a file.. only do this in the install script so it
				# knows if this has been enabled before or not
				return
		elif set=='enable' or set==True:
			if os.path.isfile(pydir+"/optin"):
				# technically should check the sanity of this file
				# print("File already there, tracking enabled")
				return
			elif os.path.isfile(pydir+"/optout"):
				# check if ID has already been created. if note, do that
				# print("rename file if it exists")
				os.rename(pydir+"/optout",pydir+"/optin")
			else:
				# create the file and ID
				# print("Create new optin file")
				f = open(pydir+"/optin", 'w') # make new file, empty
				f.close()
	except:
		pass

def checkForUpdate():
	addon_prefs = bpy.context.user_preferences.addons[__package__].preferences
	try:
		if addon_prefs.checked_update:
			return addon_prefs.update_avaialble
		else:
			addon_prefs.checked_update = True
			import urllib.request
			d = urllib.request.urlopen("http://www.theduckcow.com/data/mcprepinstall.html",timeout=10).read().decode('utf-8')
			vtmp1 = d.split('(')
			vtmp1 = vtmp1[1].split(')')[0]
			vtmp2 = ver.split('(')
			vtmp2 = vtmp2[1].split(')')[0]
			if vtmp1 != vtmp2:
				if v:print("MCprep not outdated")
				# create the text file etc.
				addon_prefs.update_avaialble = True
				return True
			else:
				if v:print("MCprep is outdated")
				addon_prefs.update_avaialble = False
				return False
	except:
		pass

########
# Toggle optin/optout for analytics
class toggleOptin(bpy.types.Operator):
	"""Toggle anonymous usage tracking to help the developers, disabled by default. The only data tracked is what functions are used, and the timestamp of the addon installation"""
	bl_idname = "object.mc_toggleoptin"
	bl_label = "Toggle opt-in for analytics tracking"

	def execute(self, context):
		if checkOptin():
			tracking(set='disable')
			usageStat('opt-out')
		else:
			tracking(set='enable')
			usageStat('opt-in')
		return {'FINISHED'}



########
# quickly open release webpage for update
class openreleasepage(bpy.types.Operator):
	"""Go to the MCprep page to get the most recent release and instructions"""
	bl_idname = "object.mcprep_openreleasepage"
	bl_label = "Open the MCprep release page"

	def execute(self, context):
		try:
			import webbrowser
			webbrowser.open("https://github.com/TheDuckCow/MCprep/releases")
		except:
			pass
		return {'FINISHED'}



def register():
	# start with custom icons
	if conf.v:print("MCprep register complete")

def unregister():

	if conf.v:print("MCprep register complete")
	
