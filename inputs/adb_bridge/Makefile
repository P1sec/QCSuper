CC := $(HOME)/ndk/bin/arm-linux-androideabi-clang

adb_bridge: adb_bridge.c
	$(CC) adb_bridge.c -std=c99 -Werror -fPIE -pie -o adb_bridge
