# Run tests and update the latest material mapping files

# Update the material mapping file, highlight misses
# python3 mcprep_data_refresh.py --auto

# Run all tests but only on the first blender instance
# ./run_tests.sh
# ./run_tests.sh -v # to include verobse printouts

# Run all tests on all versions of blender
# ./run_tests.sh -all

# Run only a single unit test within the first version of blender listed
# ./run_tests.sh -run change_skin

# Run only a single unit test, but across all blender versions
# ./run_tests.sh -all -run change_skin

TEST_ALL=$1 # pass in -all or only does first


VERSIONS=(
	"/Applications/blender 2.80/Blender.app/Contents/MacOS/Blender"
	"/Applications/blender 2.79/Blender.app/Contents/MacOS/Blender"
	"/Applications/blender 2.82/Blender.app/Contents/MacOS/Blender"
	"/Applications/blender 2.90alpha/Blender.app/Contents/MacOS/Blender"
	#"/Applications/blender 2.72/Blender.app/Contents/MacOS/Blender"
	)

# update the mappings
./mcprep_data_refresh.py -auto

# first, do a soft reload of python files
echo "Soft py file reload"
cd MCprep_addon
./reload.py -light
cd ../

# remove old test results
rm test_results.tsv
echo -e "blender\tfailed_test\tshort_err" > test_results.tsv

for ((i = 0; i < ${#VERSIONS[@]}; i++))
do
    echo "RUNNING TESTS with blender: ${VERSIONS[$i]}"
    # -b for background, -y for auto run py scripts, -P for running test script
	"${VERSIONS[$i]}" -b -y -P test_files/addon_tests.py -- --auto_run $1 $2 $3 $4
	echo "FINISHED ALL TESTS FOR blender: ${VERSIONS[$i]}"
	echo ""
	if [ -z "$TEST_ALL" ] || [ "$TEST_ALL" != "-all" ]
	then
		echo "-all not specified, skipping further blender version tests"
		exit
	fi
done

open test_results.tsv
