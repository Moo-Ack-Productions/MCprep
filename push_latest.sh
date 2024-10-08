#!/bin/bash
source venv/bin/activate

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# Validate and build the release.
# -----------------------------------------------------------------------------

# Affirm on the master branch
BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [ "$BRANCH" != "master" ]; then
    echo -e "${RED}Not on master branch, run:${NC}"
    echo "git checkout master"
    exit
fi

git pull --quiet
echo ""
echo "Current status (should be empty!)"
git status


echo "Running tests"
python run_tests.py -a
if [ $? -eq 0 ]; then
    echo "Tests passed, moving on"
else
    echo "Tests failed, exiting"
    exit
fi

# -----------------------------------------------------------------------------
# Update the data mapping to the latest values
# -----------------------------------------------------------------------------

# Manual override: we must recheckout some files after test runs finished,
# due to some side effects of testing with local code references.
git checkout MCprep_addon/MCprep_resources/mcprep_data_update.json
git checkout test_files/test_data/jmc2obj_test_1_15_2.mtl
git checkout test_files/test_data/mineways_test_combined_1_15_2.mtl
git checkout test_files/test_data/mineways_test_separated_1_15_2.mtl

python mcprep_data_refresh.py -auto

# -----------------------------------------------------------------------------
# Build releasE with translation updates
# -----------------------------------------------------------------------------

echo "Force remove trcaker files, in case they are left over"
rm MCprep_addon/mcprep_addon_tracker.json
rm mcprep_addon_trackerid.json

echo "Building prod addon..."
bab -b translate # No --during-build dev to make it prod.
if [ $? -eq 0 ]; then
    echo "Build complete"
    ls build/MCprep_addon.zip
else
    echo "Build failed"
    exit
fi

# -----------------------------------------------------------------------------
# Cross check no local changes, such as updated translations
# -----------------------------------------------------------------------------

ANY_DIFF=$(git diff MCprep_addon/MCprep_resources/mcprep_data_update.json)
if [ -z "$ANY_DIFF" ]
then
      echo ""
else
      echo "Commit new updates to mapping file before release:"
      echo "$ANY_DIFF"
      exit
fi

if [[ `git status --porcelain` ]]; then
  echo "There are uncommited changes/untracked local files"
  # exit # TODO: Enforce in future directly.
fi

# -----------------------------------------------------------------------------
# Commence release draft
# -----------------------------------------------------------------------------

echo ""
echo "Last 5 live tags online:"
git tag -l | tail -5

echo ""
# Extract the numbers between parentheses, replace comma and space with period
BASE_VER=$(grep "\"version\":" MCprep_addon/__init__.py | awk -F"[()]" '{print $2}' | tr ',' '.' | tr -d ' ')
NEW_TAG="${BASE_VER}"

ALL_TAGS=$(git tag -l)
if [[ $ALL_TAGS == *$NEW_TAG* ]]; then
    echo "Version $NEW_TAG already exists, need to update __init__.py"
    exit 1
fi

echo -e "Current __init__ version: ${GREEN}${NEW_TAG}${NC}"
read -p "Continue (Y/N): " confirm && [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]] || exit 1

NEW_NAME="MCprep_addon_$NEW_TAG.zip"
mv build/MCprep_addon.zip "build/$NEW_NAME"

# Make the tags
echo ""
echo "Generating tags and DRAFT release on github"
# use --generate-notes to auto generate release notes (edit for public changelog)
gh release create "$NEW_TAG" \
    --draft \
    --generate-notes \
    -t "v${BASE_VER} | (Update)" \
    "./build/$NEW_NAME"

echo ""
echo "Complete release by going to the link above, and updating these pages:"
echo "https://theduckcow.com/dev/blender/mcprep-download/"
echo "https://theduckcow.com/dev/blender/mcprep/releases/"
