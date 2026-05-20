@echo off
setlocal

call "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat" -arch=x64
if errorlevel 1 exit /b %errorlevel%

set "JAVA_HOME=C:\tmp\naturavision-android-toolchain\jdk17\jdk-17.0.19+10"
set "ANDROID_HOME=C:\tmp\naturavision-android-sdk"
set "ANDROID_SDK_ROOT=C:\tmp\naturavision-android-sdk"
set "PATH=%JAVA_HOME%\bin;%ANDROID_HOME%\platform-tools;%ANDROID_HOME%\cmake\3.22.1\bin;%PATH%"

call gradlew.bat --no-daemon --console=plain :app:testDebugUnitTest :app:assembleDebug :app:assembleDebugAndroidTest
