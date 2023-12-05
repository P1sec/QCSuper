#!/bin/sh

set -ex
cd "$(dirname "$0")"

# This will fetch the latest versions of tools present in the external/ dir.

cd adb

rm -rf *

wget https://dl.google.com/android/repository/platform-tools-latest-darwin.zip
unzip platform-tools-latest-darwin.zip
mv platform-tools/adb adb_macos
mv platform-tools/lib lib
rm -r platform-tools*

wget https://dl.google.com/android/repository/platform-tools-latest-linux.zip
unzip platform-tools-latest-linux.zip
mv platform-tools/adb adb_linux
rm -r platform-tools*

wget https://dl.google.com/android/repository/platform-tools-latest-windows.zip
unzip platform-tools-latest-windows.zip
mv platform-tools/adb.exe adb_windows.exe
mv platform-tools/Adb*.dll .
rm -r platform-tools*
