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

## Use of AI in Development
Since 2023, AI (Artificial Intelligence) and LLMs (Large Language Models) have surged in popularity and become more common place in development. AI can be an extremely useful tool for developers, especially when used in conjunction with existing knowledge, but it can also be a hindrance with the regards to the quality of generated code. With these in mind, we allow AI for pull requests with the following conditions:
- The AI is supplemental to the developer's work, not the other way around.
- The developer is able to modify the generated code based on the requests given in review.
- The code remains mostly human written, with the AI being used to generate boilerplate code or to help with repetitive tasks. 

Overall, AI contributions will be treated with the same level of scrutiny as contributions from humans, with regards to meaningfulness and quality. Contributors should keep in mind what they're doing in the code, and that the change makes sense. For example, throwing a file into an AI with the prompt "Optimize this" will be rejected, as what's being "fixed" isn't clear, and is a lazy change.

A good rule of thumb is this: if it's a lazy use of AI given the size of the change, then it's not a good use of AI.

Avoid the following:
- Using AI before having an idea of what change or problem you are solving
- Becoming dependent on the AI 
- Using generated code you don't understand
- Using AI exclusively without manual work 
- Etc.

So long as these guidelines are followed, all is good with regards to using AI.

## Keeping MCprep compatible

MCprep is uniquely made stable and functional across a large number of versions of blender. As of April 2022, it still even supports releases of Blender 2.8 while simultaneously supporting Blender 3.5+, and everything in between.

This is largely possible for a few reasons:

1. Automated tests plus an automated installer makes ensures that any changes that break older versions of blender will be caught automatically.
1. Abstracting API changes vs directly implementing changes. Instead of swapping "group" for "collection" in the change to blender 2.8, we create if/else statements and wrapper functions that fetch the attribute that exists based on the version of blender. Want more info about this? See [the article here](https://theduckcow.com/2019/update-addons-both-blender-28-and-27-support/).

## Compiling and running tests

As above, a critical component of maintaining support and ensuring the wide number of MCprep features are stable, is running automated tests.

### Compile MCprep using scripts

MCprep uses the [bpy-addon-build](https://github.com/Moo-Ack-Productions/bpy-build) package to build the addon, which makes it fast to copy the entire addon structure the addon folders for multiple versions of blender.

The benefit? You don't have to manually navigate and install zip files in blender for each change you make - just run the command and restart blender. It *is* important you do restart blender after changes, as there can be unintended side effects of trying to reload a plugin.

As a quick start:

```bash
# Highly recommended, create a local virtual environment (could also define globally)
python3 -m pip install --user virtualenv

python3 -m venv ./venv  # Add a local virtual env called `venv`
python3 -m pip install --upgrade pip  # Install/upgrade pip

# Activate that environment
## On windows:
.\venv\Scripts\activate
## On Mac/linux:
source venv/bin/activate

pip install -r requirements.txt

# Now with the env active, do the pip install (or upgrade)
pip install --upgrade bpy-addon-build

# Finally, you can compile MCprep using:
bab -b dev # Use dev to use non-prod related resources and tracking.
bab -b dev translate # Dev, with translations
bab -b translate # For production
```

Moving forward, you can now build the addon for all intended supported versions using: `bpy-addon-build -b dev`

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


1. Checkout dev, and commit the correct release version in `MCprep_addon/__init__.py` (should match a corresponding milestone)
1. Create a pull request to merge dev into master. This can be approved and merged without review, since all code is already reviewed - but only TheDuckCow may do this bypass with current repo permissions
1. Locally, check out master and run `git pull`
1. Run all local unit tests using `python run_tests.py -a`
  - While we do have remote github unit tests, TheDuckCow has many more versions locally for wider testing to be more comprehensive. But, github action unittests can be used in a standin if necessary.
1. Create a new UAT issue from [issues here](https://github.com/Moo-Ack-Productions/MCprep/issues/new/choose) with the name of the corresponding milestone
  - The automated test results above should be pasted into the last section of this UAT form.
  - If not all UAT steps pass, consider halting the release and/or updating/creating new issues
1. If all UAT steps pass, the run `./push_latest.sh` in the repo root
  - Follow the script's instructions and prompts for ensuring the release completes
  - You will likely need to update POT files and the json mapping via `mcprep_data_refresh.py` which gets called from within this script. Make a new PR if appropriate.
1. After this script has finished, go to [github releases](https://github.com/Moo-Ack-Productions/MCprep/releases) and edit the draft release to hand hand-adjusted changelogs
1. Press release
   1. **Immediately** download and install an old release MCprep, and install into blender (restart blender too)
   1. Make sure that the trigger to update MCprep to the new version is working.
   1. If it works, then **immediately update** the https://theduckcow.com/dev/blender/mcprep-download/ page to point to the new number (must be manually updated by TheDuckCow).
   1. Anything wrong? Immediately delete the entire release, and as a second step, also delete the tag (you likely want to copy the markdown text of the release though to a safe temporary space, so you don't lose that). You can do both steps from the github UI.
1. After release, enter hypercare by monitoring the discord channel and the datastudio dashboard for error reporting (only core contributors will have access to this)
1. git checkout dev, and then upversion the dev branch to a unique incremental version. So if you just released v3.3.1, then the dev branch should be updated to be (3, 3, 1, 1) so that we can tell official releases apart from dev versions.


## Creating your blender_execs.txt

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

- Only the mac `run_tests.sh` script has the `-all` optional flag. By default, the mac script will only install the first line in the file.

One other detail: MCprep uses Git LFS or Large File Storage, to avoid saving binary files in the git history. Some Windows users may run into trouble when first pulling.

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

Here's a template some MCprep developers found that can help (modified for simplicity) by using # to define which is the limit Git can display for each line:
```
# Title: Summary, imperative, start upper case, don't end with a period
# No more than 50 chars. #### 50 chars is here:  #

# Body: Explain *what* and *why* (not *how*). Include task ID (Jira issue).
# Wrap at 72 chars. ################################## which is here:  #

```
Add this to a file called .gitmessage, and then execute the following command:
`git config --local commit.template /path/to/.gitmessage`

To use for each commit, you can use `git config --local commit.verbose true` to tell Git to perform a verbose commit all the time for just the MCprep repo. 


## Signing Off Commits
Signing off of all commits, although not required, is good practice to certify the origin of a change. When you sign off of a commit, you certify that the commit was made in line with the Developer's Certificate of Origin:

> Developer's Certificate of Origin 1.1
> By making a contribution to this project, I certify that:
>
> a. The contribution was created in whole or in part by me and I have the right to submit it under the open source license indicated in the file; or \
> b. The contribution is based upon previous work that, to the best of my knowledge, is covered under an appropriate open source license and I have the right under that license to submit that work with modifications, whether created in whole or in part by me, under the same open source license (unless I am permitted to submit under a different license), as indicated in the file; or \
> c. The contribution was provided directly to me by some other person who certified (a), (b) or (c) and I have not modified it. \
> d I understand and agree that this project and the contribution are public and that a record of the contribution (including all personal information I submit with it, including my sign-off) is maintained indefinitely and may be redistributed consistent with this project or the open source license(s) involved.

If indeed the change was made in line with the Developer's Certificate of Origin, add the following at the end of the commit:
```
Signed-off-by: Random J Developer <random@developer.example.org>
```

**This much be your real name and a working email address.**

This can also be added with the `--signoff flag`:
```
$ git commit --signoff -m "Commit message"
```

If the change was given to you by someone else, and you have permission to contribute it here, that change must be signed off by the person who gave the change to you, and anyone before that (basically a chain of sign offs). Example:
```
<commit message and summery by John Doe, who recieved the change from Jane Doe>

Signed-off-by: John Doe <johndoe@email.com>
Signed-off-by: Jane Doe <janedoe@email.com>
```

If multiple authors were involved in writing the change, then `Co-developed-by` must be present for both you and any other authors involved in the change. As an example with 2 authors:
```
<commit message and summery>

Co-developed-by: John Doe <johndoe@email.com>
Signed-off-by: John Doe <johndoe@email.com>
Co-developed-by: Jane Doe <janedoe@email.com>
Signed-off-by: Jane Doe <janedoe@email.com>
```

## Dependencies
If you're using an IDE, it's recommened to install `bpy` as a Python module. In our experience, the [fake-bpy package](https://github.com/nutti/fake-bpy-module) seems to be the best.

It's also recommened to use a virtual environment (especially if you're on Linux) as to avoid issues with system wide packages and different versions of `bpy`. [See this for more details](https://realpython.com/python-virtual-environments-a-primer/)

There are 2 methods to do this:
- Poetry
- Manualy

Both are listed here.

### With Poetry
[Poetry](https://python-poetry.org/) is a useful tool that allows easy dependency handling. To quote the website:

>  Python packaging and dependency management made easy 

If you decide to use Poetry, then simply run the following command:

`poetry install`

To enable the virtual environment, run `poetry shell`, then type `exit` when you're done. 

### Manual: Requirements.txt Edition
First create a virtual environment:

`python3 -m venv mcprep_venv_2.80`

We use the name `mcprep_venv_2.80` to follow MCprep convention. Check the next section if you're curious the why.

To enable:

Windows: `mcprep_venv_<version>\Scripts\activate`

MacOS and Linux: `source mcprep_venv_<version>/bin/activate`

To disable: `deactivate`

Install dependencies:

`python3 -m pip install -r requirements.txt`

### Manual: Setting up `bpy` Manually Edition
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
