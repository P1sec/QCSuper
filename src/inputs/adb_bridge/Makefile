# CC := $(HOME)/ndk/toolchains/llvm/prebuilt/linux-x86_64/bin/armv7a-linux-androideabi16-clang
# Added option to compile for 64-bit ARM
CC := ~/Documents/android-ndk-r28b-linux/android-ndk-r28b/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android21-clang

adb_bridge: adb_bridge.c
	$(CC) adb_bridge.c -std=c99 -Werror -fPIE -pie -o adb_bridge
