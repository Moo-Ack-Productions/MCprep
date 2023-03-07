# Contributing to MCprep

Thanks for your interest in helping build and extend this addon! MCprep welcomes new contributions, but please be aware that are new additions will be reviewed and may have changes requested of the original owners.

## How to contribute

1. Fork MCprep
1. Copy over the `MCprep_resources` folder from the latest live release of MCprep into your local `MCprep_addon/` folder of your cloned git repo. Necessary, as these assets are not saved to git lfs yet.
1. Make changes in your own repository in the forked `dev` branch (NOT master, which matches only released, typically outdated code)
1. Test your changes (including updating `compile.sh` and `compile.bat` if needed)
1. Create a pull request back to MCprep:dev with your changes (if you choose the wrong branch, maintainers will fix that for you)
1. ~ Await review ~
1. On review, make any requested changes from maintainers. Maintainers may directly push changes to your fork if minimal.
1. When ready, maintainers will merge the code on your behalf
1. Eventually, your code will make it into the next MCprep release, congrats!

When it comes to code being reviewed, expect some discussion! If you want to contribute code back but you are not done yet, or want advice, go ahead and start your pull request and clarify it's in draft format - maintainers will likely jump in and give some steering advice. It's a good learning opportunity, but if the review process is getting too lengthy for your liking, don't hesitate to let maintainers know and we can take a more pragmatic approach (such as maintainers making the changes they are requesting, but likely at a slower rate).

## Keeping MCprep compatible

MCprep is uniquely made stable and functional across a large number of versions of blender. As of April 2022, it still even supports releases of Blender 2.79 while simultaneously supporting Blender 3.1+, and everything in between.

This is largely possible for a few reasons:

1. Automated tests plus an automated installer makes ensures that any changes that break older versions of blender will be caught automatically.
1. Abstracting API changes vs directly implementing changes. Instead of swapping "group" for "collection" in the change to blender 2.8, we create if/else statements and wrapper functions that fetch the attribute that exists based on the version of blender. Want more info about this? See [the article here](https://theduckcow.com/2019/update-addons-both-blender-28-and-27-support/).
1. No python annotations. This syntax wasn't supported in old versions of python that came with blender (namely, in Blender 2.7) and so we don't use annotations in this repository. Some workarounds are in place to avoid excessive printouts as a result.

## Internal Rewrites
MCprep has a separate branch for internal rewrites based on the dev branch. Sometimes, internal tools are deprecated, and requires features to be changed to reflect those deprecations.

Developers should not worry about this. If a features uses depracated features, it will be fixed in the next internal rewrite. 

It may be tempting to try and use the `internal-rewrites` branch to write new features. Don't, as pull requests for `internal-rewrites` will only be accepted if they deal with rewriting parts of MCprep itself. Pull requests for new features that only use `internal-rewrites` for the sake of avoiding the use of deprecated features will not be accepted.

Also, when something is deprecated, it will still remain in MCprep for one full version and be removed by the next release. For instance, if during the development of MCprep X a feature is deprecated, then that feature will only be removed officially starting with the development of MCprep Y. Thus, any new features in MCprep X that use a deprecated feature will be fixed in the `internal-rewrites` branch for the development cycle of MCprep Y.

There will also be a pull request for `internal-rewrites` for each devlopment cycle of MCprep. This pull request will contain all newly deprecated and removed features, as well as their replacements. This exists as a heads up to developers so that they know what to expect.

New features go into the `dev` branch, rewriting of old features to account for deprecations go into the `internal-rewrites` branch. When in doubt, simply ask.

## Compiling and running tests

As above, a critical component of maintaining support and ensuring the wide number of MCprep features are stable, is running automated tests.

### Compile MCprep using scripts

Scripts have been created for Mac OSX (`compile.sh`) and Windows (`compile.bat`) which make it fast to copy the entire addon structure the addon folders for multiple versions of blender. You need to use these scripts, or at the very least validate that they work, as running the automated tests depend on them.

The benefit? You don't have to manually navigate and install zip files in blender for each change you make - just run this script and restart blender. It *is* important you do restart blender after changes, as there can be unintended side effects of trying to reload a plugin.

Want to just quickly reload some files after only changing python code (no asset changes)? Mac only: Try running `compile.sh -fast` which will skip copying over the resources folder and skip zipping the addon.

### Run tests

You run the main test suite by running the wrapper `run_tests.sh` file (mac) or `run_tests.bat` (windows). This will automatically run the corresponding `compile` script which will copy code from your MCprep git repo into the different blender addons folders, and then one by one (if `run_tests.sh -all` is used on mac) it will test each version of blender to see if things are still working. At the end, you get a csv file that indicates which tests fail or passed, broken down by blender version.

Note: the windows `run_tests.bat` script always tests across all versions of blender, there is not currently a way to run the tests for only a single version of blender (unless of course, you only have one version of blender listed in your `blender_execs.txt` file).

There are a couple flaky tests, but the goal is to reduce this over time. This includes the "import_mineways_combined" test, which does not pass but is a reminder to try and improve that test specifically. All other tests should pass.

If all tests successfully complete, you'll get a csv file like so:

```
blender	failed_test	short_err
(3, 1, 0)	ALL PASSED	-
(3, 0, 0)	ALL PASSED	-
(2, 93, 0)	ALL PASSED	-
(2, 92, 0)	ALL PASSED	-
(2, 90, 1)	ALL PASSED	-
(2, 80, 75)	ALL PASSED	-
```

If there are some unit tests that failed, it might look more like so (in this case, there was only one failed test and it was the same across blender versions, showing it's a consistent problem):

```
blender	failed_test	short_err
(3, 1, 0)	import_mineways_combined	unmapped than mapped
(3, 0, 0)	import_mineways_combined	unmapped than mapped
(2, 93, 0)	import_mineways_combined	unmapped than mapped
(2, 92, 0)	import_mineways_combined	unmapped than mapped
(2, 90, 1)	import_mineways_combined	unmapped than mapped
(2, 80, 75)	import_mineways_combined	unmapped than mapped
```


### Run a specific test quickly

Working on a new test? Or maybe one specific test is failing? It's convenient to be able to run that one test on its own quickly to see if your problem is resolved, which you can do with a command like `.\run_tests.bat -run spawn_mob` (works on Mac's `run_tests.sh` script too).


### **NOTE!**

In order to run these tests, **you must ensure your git folder with your MCprep code is in a safe spot, outside of the blender install folders**. This is because the install script will attempt to remove and then copy the addon back into the blender addons folder. Tests will directly load some modules from the git repo folder structure (not from the addons folder), others which use operator calls are using the installed module code in blender itself.


## Releasing MCprep

At the moment, only the project lead (TheDuckCow) should ever mint new releases for MCprep. However, the steps are noted here for completeness:

1. All releases need a corresponding milestone, like v3.3.1
1. Make sure the version is the correct number for the release (should match a corresponding milestone). Make this commit on the dev branch.
1. Create a pull request and merge dev into master (without deleting the dev branch). Close out any remaining corresponding milestones. Add this pull request to the milestone, only merging when all other tasks are completed or moved out of the milestone.
1. Check out master, git pull
1. Make sure that `"dev" = False` in conf.py, so that prod resources are used for reporting (it should always be this way on the master branch without doing anything, even after doing a merge from dev; but *always* double check)
1. Create [a draft release](https://github.com/TheDuckCow/MCprep/releases/new) on GitHub
   - Tag is in the form `3.3.1`, no leading `v`.
   - The title however is in the form `MCprep v3.3.0 | ShortName` where version has a leading `v`.
   - Copy the body fo the description from the prior release, and then update the text and splash screen (if a major release). Edit a prior release without making changes to get the raw markdown code, e.g. [from here](https://github.com/TheDuckCow/MCprep/releases/edit/3.3.0).
1. Run `compile.sh` or `compile.bat` with no fast flag, so it does the full build
1. Run all tests, ideally on two different operating systems. Use the `./run_tests.sh -all` flag to run on all versions of blender
1. If all tests pass, again DOUBLE CHECK that "dev" = false in conf.py, then
1. Drag and drop the generated updated zip file onto github.
1. Rename so it's in the form including its version number, e.g. `MCprep_addon_v3.3.0.zip`
1. Press publish release
   1. **Immediately** download and install an old release MCprep, and install into blender (restart blender too)
   1. Make sure that the trigger to update MCprep to the new version is working.
   1. If it works, then **immediately update** the https://theduckcow.com/dev/blender/mcprep-download/ page to point to the new number (must be manually updated by TheDuckCow).
   1. Anything wrong? Immediately delete the entire release, and as a second step, also delete the tag (you likely want to copy the markdown text of the release though to a safe temporary space, so you don't lose that). You can do both steps from the github UI.
1. After release, enter hypercare by monitoring the discord channel and the datastudio dashboard for error reporting (only core contributors will have access to this)
1. git checkout dev, and then upversion the dev branch to a unique incremental version. So if you just released v3.3.1, then the dev branch should be updated to be (3, 3, 1, 1) so that we can tell official releases apart from dev versions.



## Creating your blender_installs.txt and blender_exects.txt


Your `blender_installs.txt` defines where the `compile.sh` (Mac OSX) or `compile.bat` (Windows) script will install MCprep onto your system. It's a directly copy-paste of the folder.

On a mac? The text file will be generated automatically for you if you haven't already created it, based on detected blender installs. Otherwise, just create it manually. It could look like:

```
/Users/your_username/Library/Application Support/Blender/3.1/scripts/addons
/Users/your_username/Library/Application Support/Blender/3.0/scripts/addons
/Users/your_username/Library/Application Support/Blender/2.93/scripts/addons
/Users/your_username/Library/Application Support/Blender/2.92/scripts/addons
/Users/your_username/Library/Application Support/Blender/2.90/scripts/addons
/Users/your_username/Library/Application Support/Blender/2.80/scripts/addons
/Users/your_username/Library/Application Support/Blender/2.79/scripts/addons
/Users/your_username/Library/Application Support/Blender/2.78/scripts/addons
/Users/your_username/Library/Application Support/Blender/2.72/scripts/addons
```

Your `blender_execs.txt` defines where to find the executables used in the automated testing scripts. Only these executables will be used during automated testing, noting that the testing system only supports blender version 2.8+ (sadly, only manual testing is possible in blender 2.7 with the current setup). It could look like:

```
/Applications/blender 3.1/Blender.app/Contents/MacOS/blender
/Applications/blender 3.0/Blender.app/Contents/MacOS/Blender
/Applications/blender 2.93/Blender.app/Contents/MacOS/Blender
/Applications/blender 2.90/Blender.app/Contents/MacOS/Blender
/Applications/blender 2.80/Blender.app/Contents/MacOS/Blender
```

You don't necessarily have to have all these versions of blender installed yourself, maintainers will execute the full amount of tests, but it's a good idea to at least have one version of blender 2.8, 2.9, and 3+ in the mix so you know your code will work backwards. If it doesn't, that's fine too, work with maintainers on how to add version checks (which will just disable your changes for older versions of blender).

Also note that the first line indicates the only version of blender that will be used for testing unless `-all` is specified (only for the OSX script; the `run_tests.bat` script will always test all versions of blender listed).


## Development on Windows and Mac

Support for development and testing should work for both platforms, just be aware the primary development of MCprep is happening on a Mac OSX machine, so the mac-side utility scripts have a few more features than windows:

- Only the mac `compile.sh` script has the `-fast` option to quickly reload python files (it won't copy over the blends, textures, and won't create a new zip file, all of which can be slow)
- Only the mac `compile.sh` has the feature of auto-detecting local blender executable installs. This is because on windows, there is a lot of variability where blender executables may be placed, so it should just be manually created anyways.
- Only the mac `run_tests.sh` script has the `-all` optional flag. By default, the mac script will only install the 

One other detail: MCprep uses git lfs or Large File Storage, to avoid saving binary files in the git history. Some Windows users may run into trouble when first pulling.

- If using Powershell and you cloned your repo using SSH credentials, try running `start-ssh-agent` before running the clone/pull command (per [comment here](https://github.com/git-lfs/git-lfs/issues/3216#issuecomment-1018304297))
- Alternatively, try using Git for Windows and its console.

Run into other gotchas? Please open a [new issue](https://github.com/TheDuckCow/MCprep/issues)!


## Commit Messages
Git commits should explain why a change was made, because the diff will show the changes made. For example, instead of writing:
```
Added ability to "import" MTL files
```

Instead do:
```
Added the ability to "import" MTL files

MCprep's file explorer shows both OBJs and MTLs, and sometimes users end up clicking
MTL files. This brings a quality of life improvement to change the extension
if the file selected is an MTL, since MTLs share the same name as their corresponding
OBJ files
```

The first line is a summary of the changes, and should be less then 50 characters. The rest should justify the changes. Convince us why these changes are important and why they've been made this way.

Git won't automatically wrap messages either, so each line should have a limit of 72 characters.

Here's a template I found that can help (modified for simplicity) by using # to define which is the limit Git can display for each line:
```
# Title: Summary, imperative, start upper case, don't end with a period
# No more than 50 chars. #### 50 chars is here:  #

# Body: Explain *what* and *why* (not *how*). Include task ID (Jira issue).
# Wrap at 72 chars. ################################## which is here:  #

```
Add this to a file called .gitmessage, and then execute the following command:
`git config --local commit.template /path/to/.gitmessage`

To use for each commit, you can use `git config --local commit.verbose true` to tell Git to perform a verbose commit all the time for just the MCprep repo.

## IDE Support
If you're using an IDE, it's recommened to install `bpy` as a Python module. In my (StandingPad) experiance, the [fake-bpy package](https://github.com/nutti/fake-bpy-module) seems to be the best.

It's also recommened to use a virtual environment (especially if you're on Linux) as to avoid issues with system wide packages and different versions of `bpy`. [See this for more details](https://realpython.com/python-virtual-environments-a-primer/)

### Creating a Virtual Environment and Setting up `bpy`
First, we need to come up with a name. For MCprep development, it's recommended to use the following convention:
`mcprep_venv_<version>`

This allows you to have multiple versions of `bpy` side by side in their own environments.

For example, if I was making a virtul environment for 3.3, I would do `mcprep_venv_3.3`.

To create a virtual environment, do the following:

`python3 -m venv mcprep_venv_<version>`

Then to enable it, then:

Windows: `mcprep_venv_<version>\Scripts\activate`

MacOS and Linux: `source mcprep_venv_<version>/bin/activate`

This will make your terminal use the virtual environment until you close it or use `deactivate`. Each time you open your terminal after this, remember to enable the virtual environment

Next we need to install `fake-bpy`:

`python3 -m pip install fake-bpy-module-<version>`

If you use PyCharm, you should check the GitHub for [additional instructions](https://github.com/nutti/fake-bpy-module#install-via-pip-package)

Now you're ready to do MCprep development
