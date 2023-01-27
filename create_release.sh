wget "https://github.com/TheDuckCow/MCprep/releases/download/3.4.1/MCprep_addon_v3.4.1.zip"
mkdir MCprep_stable_release
unzip ./MCprep_addon_v3.4.1.zip -d MCprep_stable_release
mv ./MCprep_stable_release/MCprep_addon/MCprep_resources/** ./MCprep_addon/MCprep_resources
rm -rf ./MCprep_stable_release MCprep_addonv3.4.1.zip
