:: Run all blender addon tests
::
:: %1: pass in -all or e.g. -single or none, to only do first blender exec only.
:: %2: Decide which specific test class+case to run, defined in py test files.

set RUN_ALL=%1
set RUN_ONLY=%2

echo Doing initial reinstall of addon
::call compile.bat

:: Text file where each line is a path to a specific blender executable (.exe)
set BLENDER_EXECS=blender_execs.txt

set TEST_RUNNER="test_files\addon_tests.py"
echo "Starting tests"

set "file=%BLENDER_EXECS%"
:: TODO: implement RUN_ALL control.
for /F "usebackq delims=" %%a in ("%file%") do (
	echo Doing test for %%a
	"%%a" -b -y -P %TEST_RUNNER% -- --auto_run  %1 %2 %3 %4
)

goto:eof
