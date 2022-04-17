:: Script to automatically install an addon to multiple blender versions.
@echo off

:: Name for subfolders as well as the install folder under \addons\
set NAME=MCprep_addon

:: One line per blender roaming folder, e.g:
:: C:\Users\...\AppData\Roaming\Blender Foundation\Blender\3.0\scripts\addons\
set BLENDER_INSTALLS=blender_installs.txt

:: Run the main build sequence.
call:detect_installs
call:build
call:install_all
call:clean

:: Exit before function definitions.
EXIT /B %ERRORLEVEL%


:: Function definitions -------------------------------------------------------

:: Cleanup generated files
:clean
echo Cleaning up files
rd /s /q "build\%NAME%"
goto:eof


:: Create a local build zip of the local addon.
:build
echo Running build
call:clean
if not  exist "build" (
	mkdir "build"
)
mkdir "build\%NAME%"

copy MCprep_addon\*.py "build\%NAME%\"
copy MCprep_addon\*.txt "build\%NAME%\"
xcopy /e /k /q MCprep_addon\icons\ "build\%NAME%\icons\" 
xcopy /e /k /q MCprep_addon\materials\ "build\%NAME%\materials\"
xcopy /e /k /q MCprep_addon\spawner\ "build\%NAME%\spawner\"
xcopy /e /k /q MCprep_addon\MCprep_resources\ "build\%NAME%\MCprep_resources\"

:: Built in command for windwos 10+
cd build
tar -a -cf "%NAME%.zip" -c "%NAME%" .
cd ..
echo Finished zipping, check for errors
goto:eof


:: Detect if the installs script is present.
:detect_installs
if not exist %BLENDER_INSTALLS% (
	echo The blender_installs.txt file is missing - please create it!
	EXIT /B
)
goto:eof

:: Install addon to a specific path (addons folder), delete prior install.
:install_path
set installpath=%~1
echo Installing addon to: %installpath%
rd /s /q "%installpath%\%NAME%"
mkdir  "%installpath%\%NAME%"
xcopy /e /k /q "build\%NAME%\" "%installpath%\%NAME%\" /Y
goto:eof


:: Install addon to all paths defined in config file.
:install_all
echo Installing addon to all files in blender_installs.txt
set "file=%BLENDER_INSTALLS%"

for /F "usebackq delims=" %%a in ("%file%") do (
	call:install_path "%%a"
)
goto:eof


@echo on
EXIT /B 0