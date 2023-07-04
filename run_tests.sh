#!/usr/bin/env bash
#
# Run all blender addon tests.
#
# Run all tests for only the first executable listed in blender_execs.txt
# ./run_tests.sh
#
# Run all tests on all versions of blender listed in blender_execs.txt
# ./run_tests.sh -all
#
# Run only a single unit test within the first version of blender listed
# ./run_tests.sh -run change_skin
#
# Run only a single unit test, but across all blender versions
# ./run_tests.sh -all -run change_skin
#
# Add -v to any argument above to allow print statements within tests.

# File containing 1 line per blender executable complete path. The first
# line is the blender executable that will be used in 'quick' (-single) tests.
# All executables will run all tests if TEST_ALL == "-all".
BLENDER_EXECS=blender_execs.txt
IFS=$'\n' read -d '' -r -a VERSIONS < $BLENDER_EXECS

TEST_ALL=$1 # Check later if this is -all or not


TEST_RUNNERS=(
    "test_files/addon_tests.py"
)

# Update the mappings.
python3 ./mcprep_data_refresh.py -auto

# First, do a soft reload of python files.
echo "Soft py file reload"
./compile.sh -fast


# Remove old test results.
rm test_results.tsv
echo -e "blender\tfailed_test\tshort_err" > test_results.tsv

for ((i = 0; i < ${#VERSIONS[@]}; i++))
do
    echo "RUNNING TESTS with blender: ${VERSIONS[$i]}"
    for ((j = 0; j < ${#TEST_RUNNERS[@]}; j++))
    do
        echo "Running test ${TEST_RUNNERS[$j]}"
        # -b for background, -y for auto run scripts, -P to run specific script
        "${VERSIONS[$i]}" -b -y -P "${TEST_RUNNERS[$j]}" -- --auto_run $1 $2 $3 $4
    done

    echo "FINISHED ALL TESTS FOR blender: ${VERSIONS[$i]}"
    echo ""
    if [ -z "$TEST_ALL" ] || [ "$TEST_ALL" != "-all" ]
    then
        echo "-all not specified, skipping further blender version tests"
        exit
    fi
done

echo "View results in:  test_results.csv"
open test_results.tsv
