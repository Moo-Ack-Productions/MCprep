#!/usr/bin/env bash
#
# Compile the addon into a zip and install into blender (if available).
# Will install into blender if addons paths defined by blender_installs.txt
# which should have a path that ends in e.g. Blender/2.90/scripts/addons

# To skip zipping and do a fast reload

if [ -z "$1" ] || [ "$1" != "-fast" ]
then
	echo "Running a slow compile"
	FAST_RELOAD=false
else
	echo "Running a fast compile"
	FAST_RELOAD=true
fi


while getopts 'f:d' flag
do
	case "${flag}" in 
		f) echo "Running a fast compile..." 
		   FAST_RELOAD=true
			;;
		d) DEV_BUILD=true;;
		*) echo "Invalid flag!" && exit;;
	esac

done

NAME=MCprep_addon
BLENDER_INSTALLS=blender_installs.txt

# Remove left over files in the build folder, but leaves the zip.
function clean(){
	echo "Cleaning build folder"
	rm -r build/$NAME/
}

# Create a local build zip of the local addon.
function build() {
	# If fast reloading, don't clean up old files.
	# if [ "$FAST_RELOAD" = false ]
	# then
	# 	clean
	# fi

	clean

	# Create the build dir as needed
	if [ ! -d build ]
	then
		mkdir -p build
	fi
	mkdir -p build/$NAME

	# Specific files and subfolders to copy into the MCprep build
	echo "Creating local build"

	cp $NAME/*.py build/$NAME/
	cp $NAME/*.txt build/$NAME/
	cp -r $NAME/icons build/$NAME/
	cp -r $NAME/materials build/$NAME/
	cp -r $NAME/spawner build/$NAME/

	if [ "$DEV_BUILD" = true ]
	then
		echo "Creating dev build..."
		touch build/$NAME/mcprep_dev.txt
	else
		rm -f build/$NAME/mcprep_dev.txt # Make sure this is removed
	fi

	if [ "$FAST_RELOAD" = false ]
	then
		echo "Copying resources and building zip"
		# These resources are the most intense to reload, so don't do if 'fast'
		cp -r $NAME/MCprep_resources build/$NAME/

		# Making the zip with all the sub files is also slow.
		cd build || exit
		rm $NAME.zip # Compeltely remove old version (else it's append/replace)
		zip $NAME.zip -rq $NAME
		cd ../
	fi
}


# Autogenerate the blender_installs.txt file if missing,
# populating the highest versions of blender in the file first.
# Note: For every version of blender included, one install will be made
# and potentially tested by run_tests.sh.
function detect_installs() {
	if [ ! -f "$BLENDER_INSTALLS" ]
	then
		echo "Generating new $BLENDER_INSTALLS"

		if [ "$(uname)" == "Darwin" ]
		then
		    # Add all
		    ls -rd -- /Users/*/Library/Application\ Support/Blender/*/scripts/addons/ > $BLENDER_INSTALLS
		elif [ "$(uname -s | cut -c 1-5)" == "Linux" ]
		then
			ls -rd -- ~/.config/blender/*/scripts/addons > $BLENDER_INSTALLS
			exit
		else
			echo "Unsupported platform, manually populate"
			exit
		fi
	else
		echo "Loading installs from $BLENDER_INSTALLS"
	fi
}

# Install the addon to this path
function install_path(){
	i=$1

	if [ "$FAST_RELOAD" = false ]
	then
		# echo "Remove prior: $i/$NAME/"
		# ls "$i/$NAME/"
		rm -rf "${i:?}/${NAME:?}/"
	fi

	mkdir -p "$i/$NAME"
	cp -R build/$NAME "$i/"
	echo "Installed at: $i/"
}

function install_all(){
	# Load in all target blender version(s)
	IFS=$'\n' read -d '' -r -a lines < $BLENDER_INSTALLS

	for i in "${lines[@]}"
	do
		install_path "$i"
	done
}

# Main build calls.

detect_installs
build
install_all
clean

echo "Reloaded addon"
