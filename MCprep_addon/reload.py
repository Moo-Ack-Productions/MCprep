###
# DO NOT DISTRIBUTE WITH ADDON
# This is a convenience script for reloading files into blender and packaging
# the different versions together.
#
# Simply run this python script in its own working directory
#
###

"""
todo

Make it auto-install into the blender source files

"""

from datetime import datetime
from subprocess import Popen, PIPE
import os
import codecs
import sys
import shutil


# Global vars, the things to change
name_var = "$VERSION"  # search for this in each, string
name_array = ["free","premium"]
verbose_var = "$VERBOSE" # turn line from 'v = True # $VERBOSE" to 'v = False'
addon_name = "MCprep_addon"

addonpath = "/Users/patrickcrawford/Library/Application Support/Blender/2.76/scripts/addons"
build_dir = "../compiled/"

files = ["__init__.py","conf.py","materials.py","meshswap.py","spawner.py","tracking.py",
		"mcprep_ui.py", "util.py"]



def main():

	if len(sys.argv) < 2:
		# no input args, just assume the basic level
		publish()

	elif len(sys.argv) == 2:
		if sys.argv[1] == "publish":
			publish()
		elif sys.argv[1] in name_array:
			publish(sys.argv[1])


def publish(target=""):
	print("preparing project for publishing")

	if target not in name_array:
		print("Building all")

	if os.path.isdir(build_dir)==True:
		shutil.rmtree(build_dir)
	os.mkdir(build_dir)

	# compile one or all

	#OLD CODE, no longer applicable
	# if target in name_array:
	# 	publish_version(target, install=True)
	# else:
	# 	for t in name_array:
	# 		publish_version(t)

	publish_version("", install=False)

	print("Build finished")


def publish_version(version, install=False):

	# make the staging area
	# stagepath = "addon_name"+_+version # OLD
	stagepath = addon_name
	print("Building target: "+stagepath)

	if os.path.isdir(stagepath)==True:
		shutil.rmtree(stagepath)
	os.mkdir(stagepath)

	# file by file, copy and do replacements
	for fil in files:
		if os.path.isdir(fil)==True:
			newdirname = os.path.join(stagepath, fil)
			shutil.copytree(fil, newdirname) # will have some .DS_store's
		else:
			fname = fil
			newname = os.path.join(stagepath, fil)
			inFile = codecs.open(fname, "r", "utf-8")
			outFile = codecs.open(newname, "w", "utf-8")
			for line in inFile:
				newline = do_replacements_on(line,version)
				outFile.write(newline)
			inFile.close()
			outFile.close()

	# zip and remove
	p = Popen(['zip','-r',stagepath+'.zip',stagepath],
				stdin=PIPE,stdout=PIPE, stderr=PIPE)
	stdout, err = p.communicate(b"")

	if install == True:
		installedpath = os.path.join(addonpath,addon_name+"_"+version)
		if not os.path.isdir(installedpath):
			print("creating folder:")
			print(installedpath)
			os.mkdir(installedpath)
		else:
			try:
				os.rmtree(os.path.join(addonpath,addon_name+"_"+version,\
						"__pycache__"))
			except:
				print("No cache to delete")

		for fil in files:
			stagefile = os.path.join(stagepath, fil)
			p = Popen(['mv',stagefile,installedpath],
				stdin=PIPE,stdout=PIPE, stderr=PIPE)
			stdout, err = p.communicate(b"")


	shutil.rmtree(stagepath)
	os.rename(stagepath+'.zip',os.path.join(build_dir,stagepath+'.zip'))


def do_replacements_on(line,version):
	# replace all variables as appropriate, including verbose build
	# including custom setup for demo version and 
	tmp = ""
	if name_var in line:
		nline = line.split(name_var)
		for index in range(len(nline)-1):
			tmp+= nline[index]+version.capitalize()
		tmp+= nline[-1]
	else:
		tmp = line

	return tmp


main()

