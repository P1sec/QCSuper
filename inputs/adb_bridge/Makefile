CC := $(HOME)/ndk/toolchains/llvm/prebuilt/linux-x86_64/bin/armv7a-linux-androideabi16-clang

adb_bridge: adb_bridge.c
	$(CC) adb_bridge.c -std=c99 -Werror -fPIE -pie -o adb_bridge
