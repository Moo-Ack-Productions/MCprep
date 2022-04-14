# Contributing to MCprep

Thanks for your interest in helping build and extend this addon! MCprep welcomes new contributions, but please be aware that are new additions will be reviewed and may have changes requested of the original owners.

## How to contribute

1. Fork MCprep
2. Make changes in your own repository in the forked `dev` branch (NOT master, which matches released code)
3. Test your changes (including updating `compile.sh` if needed)
4. Create a pull request back to MCprep:dev with your changes (if you choose the wrong branch, maintainers will fix that for you)
5. ~ Await review ~
6. On review, make any requested changes from maintainers.
7. When ready, maintainers will merge the code on your behalf
8. Eventually, your code will make it into the next MCprep release, congrats!

When it comes to code being reviewed, expect some discussion! If you want to contribute code back but you are not done yet, or want advice, go ahead and start your pull request and clarify it's in draft format - maintainers will likely jump in and give some steering advice.

## Keeping MCprep compatible

MCprep is uniquely made stable and functional across a large number of versions of blender. As of April 2022, it still even supports releases of Blender 2.79 while simultaneously supporting Blender 3.1+, and everything in between.

This is largely possible for a few reasons:

1. Automated tests plus an automated installer makes ensures that any changes that break older versions of blender will be caught automatically.
2. Abstracting API changes vs directly implementing changes. Instead of swapping "group" for "collection" in the change to blender 2.8, we create if/else statements and wrapper functions that fetch the attribute that exists based on the version of blender. Want more info about this? See [the article here](https://theduckcow.com/2019/update-addons-both-blender-28-and-27-support/).
3. No python annotations. This syntax wasn't supported in old versions of python that came with blender (namely, in Blender 2.7) and so we don't use annotations in this repository. Some workarounds are in place to avoid excessive printouts as a result.

## Compiling and running tests

As above, a critical component of maintaining support and ensuring the wide number of MCprep features are stable, is running automated tests.

Want to just quickly reload some files after only changing python code (no asset changes)? Try running `compile.sh -fast` which will skip copying over the resources folder and skip zipping the addon. 

You run the main test suite by running the wrapper `run_tests.sh` file. This will automatically run the `compile.sh` script which will copy code from your MCprep git repo into the different blender addons folders, and then one by one (if `run_tests.sh -all` is used) it will test each version of blender to see if things are still working. At the end, you get a csv file that indicates which tests fail or passed, broken down by blender version.

Generally speaking there are some flaky tests that can be generally and safely ignored. This includes the "import_mineways_combined" test.

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


### **NOTE!**

In order to run these tests, **you must ensure your git folder with your MCprep code is in a safe spot, outside of the blender install folders**. This is because the install script will attempt to remove and then copy the addon back into the blender addons folder.

### **NOTE!**

The automated install  and testing setup here has so far only be set up for Mac OSX. Work is being done to make the equivalent windows bat scripts to support the same behavior there.


## Creating your blender_installs.txt and blender_exects.txt


Your `blender_installs.txt` defines where the `compile.sh` script will install MCprep onto your system. It's a directly copy-paste of the folder.

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

Also note that the first line indicates the only version of blender that will be used for testing unless `-all` is specified.
