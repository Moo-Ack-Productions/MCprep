# Get the latest stable release and unzip
wget "https://github.com/TheDuckCow/MCprep/releases/download/3.4.1/MCprep_addon_v3.4.1.zip"
mkdir MCprep_stable_release
unzip ./MCprep_addon_v*.zip -d MCprep_stable_release

# Remove the files in resources
rm -rf ./MCprep_addon/MCprep_resources/**
# Move the special files
mv -f ./MCprep_stable_release/MCprep_addon/MCprep_resources/** ./MCprep_addon/MCprep_resources 
# Remove the stable release
rm -rf ./MCprep_stable_release MCprep_addon_v*.zip

# Compile the code
sh ./compile.sh
rm -rf ./MCprep_addon/MCprep_resources/**

