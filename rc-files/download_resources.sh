#!/bin/sh
# Get the latest stable release and unzip
# 
# TODO: Automatically get the latest tag and download link. Perhaps 
# through the GitHub API?
VERSION="3.6.1.2"
wget "https://github.com/Moo-Ack-Productions/MCprep/releases/download/$VERSION/MCprep_addon_$VERSION.zip"
mkdir MCprep_stable_release
unzip ./MCprep_addon_*.zip -d MCprep_stable_release

# Remove the files in resources
rm -rf ./MCprep_addon/MCprep_resources/**
# Move the special files
mv -f ./MCprep_stable_release/MCprep_addon/MCprep_resources/** ./MCprep_addon/MCprep_resources 
# Remove the stable release
rm -rf ./MCprep_stable_release MCprep_addon_*.zip

git restore MCprep_addon/MCprep_resources/Languages
git restore MCprep_addon/MCprep_resources/mcprep_data_update.json
