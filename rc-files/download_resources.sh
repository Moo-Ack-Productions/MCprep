# Get the latest stable release and unzip
wget "https://github.com/Moo-Ack-Productions/MCprep/releases/download/3.5.3/MCprep_addon_3.5.3.zip"
mkdir MCprep_stable_release
unzip ./MCprep_addon_*.zip -d MCprep_stable_release

# Remove the files in resources
rm -rf ./MCprep_addon/MCprep_resources/**
# Move the special files
mv -f ./MCprep_stable_release/MCprep_addon/MCprep_resources/** ./MCprep_addon/MCprep_resources 
# Remove the stable release
rm -rf ./MCprep_stable_release MCprep_addon_*.zip
