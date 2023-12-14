#!/bin/sh

set -ex
cd "$(dirname "$0")"

# This will fetch the latest versions of tools present in the external/ dir.

cd adb

rm -rf *

# Note: adb r34.0.4 is the latest version compatible with Windows 7
# (cf. https://github.com/Genymobile/scrcpy/issues/4391)

wget https://dl.google.com/android/repository/platform-tools_r34.0.4-darwin.zip
unzip platform-tools_r34.0.4-darwin.zip
mv platform-tools/adb adb_macos
mv platform-tools/lib64  lib64
rm -r platform-tools*

wget https://dl.google.com/android/repository/platform-tools_r34.0.4-linux.zip
unzip platform-tools_r34.0.4-linux.zip
mv platform-tools/adb adb_linux
rm -r platform-tools*

wget https://dl.google.com/android/repository/platform-tools_r34.0.4-windows.zip
unzip platform-tools_r34.0.4-windows.zip
mv platform-tools/adb.exe adb_windows.exe
mv platform-tools/Adb*.dll .
rm -r platform-tools*
