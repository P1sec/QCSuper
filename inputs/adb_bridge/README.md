This directory contains a C program which was cross-compiled to ARM, which is intended to be uploaded automatically on the Android device, in order to expose a local TCP service which will make the bridge between the `/dev/diag` device and QCSuper.

For more information on what is the `/dev/diag` device, plese read [The Diag protocol.md](../docs/The%20Diag%20protocol.md).

For seeing the Python source code performing the upload process to the Android device, you can look at [`inputs/adb.py`](../adb.py).

If you wish to recompile the C program, you can follow these steps:

* Download the latest [Android NDK toolchain](https://developer.android.com/ndk/downloads/), and [build it](https://developer.android.com/ndk/guides/standalone_toolchain) for ARM
* Execute `make CC=$clang_path` where `$clang_path` is the path to the `arm-linux-androideabi-clang` binary in the toolchain you have built.
