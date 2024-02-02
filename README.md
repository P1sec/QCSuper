# QCSuper

**QCSuper** is a tool communicating with Qualcomm-based phones and modems, allowing to **capture raw 2G/3G/4G** (and for certain models 5G) radio frames, among other things.

It will allow you to **generate PCAP** captures of it using either a rooted Android phone, an USB dongle or an existing capture in another format.

![Screenshot of using QCSuper along with Wireshark](docs/sample_pcaps/Wireshark%20screenshot.png?raw=true)

After having [installed](#installation) it, you can plug your rooted phone in USB and using it, with a compatible device, is as simple as:

```
./qcsuper.py --adb --wireshark-live
```

Or, if you have manually enabled exposing a Diag port over your phone (the corresponding procedure may vary depending on your phone modem and manufacturer, see below for more explanations), or if you have plugged a mobile broadband dongle:

```
./qcsuper.py --usb-modem auto --wireshark-live
```

It uses the Qualcomm Diag protocol, also called QCDM or DM (Diagnostic Monitor) in order to communicate with your phone's baseband.

**You are willing to report that your device works or does not work? You can open a [Github issue](https://github.com/P1sec/QCSuper/issues/new).**

## Table of contents

* **[Installation](#installation)**
  * [Ubuntu and Debian installation](#ubuntu-and-debian-installation)
  * [Windows installation](#ubuntu-and-debian-installation)
* [Supported protocols](#supported-protocols)
* **[Usage notice](#usage-notice)**

**Annexes:**

* [Using QCSuper with an USB modem](#using-qcsuper-with-an-usb-modem)
* [Supported devices](#supported-devices)
* [Related tools using the Diag protocol](#related-tools-using-the-diag-protocol)

**Blog post/demo:** [Presenting QCSuper: a tool for capturing your 2G/3G/4G air traffic on Qualcomm-based phones](https://labs.p1sec.com/2019/07/09/presenting-qcsuper-a-tool-for-capturing-your-2g-3g-4g-air-traffic-on-qualcomm-based-phones/)

**More documentation:**

* [The Diag protocol](docs/The%20Diag%20protocol.md)
* [QCSuper architecture](docs/QCSuper%20architecture.md)

## Installation

QCSuper was lately tested and developed on Ubuntu LTS 22.04 and also has been used over Windows 11. It depends on a few Python modules. It is advised to use Linux for better compatibility.

To use it, your phone must be rooted or expose a diag service port over USB. In order to check for compatibility with your phone, look up the phone's model on a site like [GSMArena](https://www.gsmarena.com/) and check whether it has a Qualcomm processor.

In order to open PCAP files produced by QCSuper, you can use any Wireshark 2.x - 4.x for 2G/3G frames, but you need at least Wireshark 2.5.x for 4G frames (and 2.6.x for individual NAS messages decrypted out of 4G frames). Ubuntu currently provides a recent enough build for all versions.

Decoding 5G frames was tested under Wireshark 3.6.x and will be done through automatically installing a Wireshark Lua plug-in (in `%APPDATA%\Wireshark\plugins` under Windows or in `~/.local/lib/wireshark/plugins` under Linux and macOS), which can be avoided through setting the `DONT_INSTALL_WIRESHARK_PLUGIN=1` environment variable if you are willing to avoid this.

### Ubuntu and Debian installation

Open a terminal and type the following:

```bash
# Download QCSuper
git clone https://github.com/P1sec/QCSuper.git qcsuper
cd qcsuper

# Install dependencies
sudo apt install python3-pip wireshark
sudo pip3 install --upgrade pyserial pyusb crcmod https://github.com/P1sec/pycrate/archive/master.zip
```

### Windows installation

QCSuper can run on Windows, but you should beforehand ensure that Google's ADB prompt correctly runs on your machine with your device, and you should as well manually create `libusb-win32` filters (through the utility accessible in the Start Menu after installing it) in the case where your device directly needs to connect to the Diag port over pseudo-serial USB.

(Please note that if you mode-switch your device, the associated USB PID/VID may change and it may require to redo driver associations in the `libusb-win32` filter creation utility - and/or in the Windows peripherial devices manager depending on the case)

On Windows, you may need (in addition to Google's ADB kernel drivers) to download and install your phone's USB drivers from your phone model (this may include generic Qualcomm USB drivers). Please search for your phone's model + "USB driver" or "ADB driver" on Google for instructions.

Then, you need to ensure that you can reach your device using `adb`. You can find a tutorial on how to download and setup `adb` [here](https://www.xda-developers.com/install-adb-windows-macos-linux/). The `adb.exe shell` (or whatever executable path you use, a copy of the ADB executable is present in the `qcsuper/inputs/external/adb` folder of QCSuper) command must display a prompt to continue.

Then, follow these links (the tool has been tested lately on Windows 11 - it is not guaranteed to work on Windows 7) in order to:

* [Install Python 3.12](https://www.python.org/ftp/python/3.12.1/python-3.12.1-amd64.exe) (Windows 7 version: [Python 3.7](https://www.python.org/ftp/python/3.7.9/python-3.7.9.exe)) or more recent (be sure to check options to include it into PATH, install it for all users and install pip)
* [Install Wireshark 4.2](https://2.na.dl.wireshark.org/win64/Wireshark-4.2.2-x64.exe) (Windows 7 version: [Install Wireshark 3.6](https://2.na.dl.wireshark.org/win64/all-versions/Wireshark-win64-3.6.19.exe)) or more recent
* [Install libusb-win32 1.2.7.3](https://github.com/mcuee/libusb-win32/releases/download/snapshot_1.2.7.3/libusb-win32-devel-filter-1.2.7.3.exe) (Windows 7 version: [libusb-win32 1.2.3.7](https://github.com/mcuee/libusb-win32/releases/download/snapshot_1.2.7.3/libusb-win32-devel-filter-1.2.7.3.exe)) or more recent
* Restart your command prompt/terminal in order to ensure that the `%PATH%` system variable has been updated.
* [Download and extract QCSuper](https://github.com/P1sec/QCSuper/archive/master.zip)

To install the required Python modules, open your command prompt and type:

```bash
pip3 install --upgrade pyserial pyusb crcmod https://github.com/P1sec/pycrate/archive/master.zip https://github.com/pyocd/libusb-package/archive/master.zip
```

Still in your command prompt, move to the directory containing QCSuper using the `cd` command. You can then execute commands (which should start with `py qcsuper.py` or `py3 qcsuper.py` if you installed Python 3 from the online installer, or `python3.exe .\qcsuper.py` if you installed it from the Windows Store).

As noted above, it is possible that you have to add a `libusb-win32` filter through the utility available in the Start Menu in order to ensure that the interface corresponding to the Diag port is visible by QCSuper on the mode-switched device (a first failed attempt to run the tool using the `--adb` flag should trigger a mode-switch if the ADB driver is working and the device is correctly rooted).

<p align="center">
<img src="docs/Adding%20libusb-win32%20filter.png?raw=true" alt="Screenshot of adding a libusb-win32 filter for the Diag port of a Mi phone">
</p>

## Supported protocols

QCSuper supports capturing a handful of mobile radio protocols. These protocols are put after a [GSMTAP header](http://osmocom.org/projects/baseband/wiki/GSMTAP), a standard header (encapsulated into UDP/IP) permitting to identify the protocol, and GSMTAP packets are put into a [PCAP file](https://wiki.wireshark.org/Development/LibpcapFileFormat) that is fully analyzable using Wireshark.

2G/3G/4G protocols can be broken into a few "layers": layer 1 is about the digital radio modulation and multiplexing, layer 2 handles stuff like fragmentation and acknowledgement, layer 3 is the proper signalling or user data.

QCSuper allows you most often to capture on layer 3, as it is the most pratical to analyze using Wireshark, and is what the Diag protocol provides natively (and some interesting information is here).

* 2G (GSM): Layer 3 and upwards (RR/...)
* 2.5G (GPRS and EDGE): Layer 2 and upwards (MAC-RLC/...) for data acknowledgements
* 3G (UMTS): Layer 3 and upwards (RRC/...)
  * Additionally, it supports reassembling SIBs (System Information Blocks, the data broadcast to all users) in separate GSMTAP frames, as Wireshark currently can't do it itself: flag `--reassemble-sibs`
* 4G (LTE): Layer 3 and upwards (RRC/...)
  * Additionally, it supports putting decrypted NAS message, which are embedded encrypted embedded into RRC packet, in additional frames: flag `--decrypt-nas`

By default, the IP traffic sent by your device is not included, you see only the signalling frames. You can include the IP traffic you generate using the `--include-ip-traffic` option (IP being barely the layer 3 for your data traffic in 2G/3G/4G, at the detail that its headers may be compressed (ROHC) and a tiny PPP header may be included).

The data traffic you send uses a channel different from the signalling traffic, this channed is setup through the signalling traffic; QCSuper should thus show you all details relevant to how this channel is initiated.

## Usage notice

In order to use QCSuper, you specify one input (e.g: `--adb` (Android phone), `--usb-modem`) and one or more modules (`--wireshark-live` for opening Wireshark, `--pcap-dump` for writing traffic to a PCAP file, `--info` for generic information about the device...).

A few commands you can type are:

```bash
# Open Wireshark directly, using a rooted Android phone as an input,
# for compatible phones:
$ ./qcsuper.py --adb --wireshark-live

# Same, but dump to a PCAP file instead of opening Wireshark directly
$ ./qcsuper.py --adb --pcap-dump /tmp/my_pcap.pcap
```

Or, if it is not simple enough to work:

```bash
# Same, but using an USB modem/phone exposing a Diag serial port
# directly over USB, in the case where the "--adb" mode does not
# work directly:

# - With a compatible Android phone where the Diag port over USB has
#   been manually enabled by the user (see the "How to manually enable
#   the diagnostic ports on my phone" section below for a summary of
#   how this may be possible with most Qualcomm-based models)
#
#   In this case, you may try:
./qcsuper.py --usb-modem auto --wireshark-live
#   Or, if selecting manually the USB device corresponding to the 
#   Diag-enabled phone turns to be requried:
$ lsusb
(..)
Bus 001 Device 076: ID 05c6:9091 Qualcomm, Inc. Intex Aqua Fish & Jolla C Diagnostic Mode
$ ./qcsuper.py --usb-modem 1d6b:0003 --wireshark-live # With vendor ID:product ID...
$ ./qcsuper.py --usb-modem 002:001 --wireshark-live # ...or with bus ID:device ID
# Or, if selecting the configuration number and interface number (referred as "bConfigurationValue" and "bInterfaceNumber" in the USB desciprtors) turn to be required:
$ lsusb -v
(..)
$ ./qcsuper.py --usb-modem 1d6b:0003:1:0 --wireshark-live # With vendor ID:product ID:configuration:interface...
$ ./qcsuper.py --usb-modem 002:001:1:0 --wireshark-live # ...or with bus ID:device ID:configuration:interface

# - With a generic serial-over-USB device where the "usbserial" module has
#   loaded a /dev/ttyUSB{0-9} device corresponding to the diagnostic port:
$ sudo ./qcsuper.py --usb-modem /dev/ttyUSB2 --wireshark-live

# - With an Option device where the "hsoserial" module has loaded a
#   /dev/ttyHS{0-9} device corresponding to the diagnostic port:
$ sudo ./qcsuper.py --usb-modem /dev/ttyHS2 --wireshark-live
```

Here is the current usage notice for QCSuper:

```
usage: qcsuper.py [-h] [--cli] [--efs-shell] [-v] (--adb | --adb-wsl2 ADB_WSL2 | --usb-modem TTY_DEV | --dlf-read DLF_FILE | --json-geo-read JSON_FILE) [--info]
                  [--pcap-dump PCAP_FILE] [--wireshark-live] [--memory-dump OUTPUT_DIR] [--dlf-dump DLF_FILE] [--json-geo-dump JSON_FILE] [--decoded-sibs-dump]
                  [--reassemble-sibs] [--decrypt-nas] [--include-ip-traffic] [--start MEMORY_START] [--stop MEMORY_STOP]

A tool for communicating with the Qualcomm DIAG protocol (also called QCDM or DM).

options:
  -h, --help            show this help message and exit
  --cli                 Use a command prompt, allowing for interactive completion of commands.
  --efs-shell           Spawn an interactive shell to navigate within the embedded filesystem (EFS) of the baseband device.
  -v, --verbose         Add output for each received or sent Diag packet.

Input mode:
  Choose an one least input mode for DIAG data.

  --adb                 Use a rooted Android phone with USB debugging enabled as input (requires adb).
  --adb-wsl2 ADB_WSL2   Unix path to the Windows adb executable. Equivalent of --adb command but with WSL2/Windows interoperability.
  --usb-modem TTY_DEV   Use an USB modem exposing a DIAG pseudo-serial port through USB.
                        Possible syntaxes:
                          - "auto": Use the first device interface in the system found where the
                            following criteria is matched, by order of preference:
                            - bInterfaceClass=255/bInterfaceSubClass=255/bInterfaceProtocol=48/bNumEndpoints=2
                            - bInterfaceClass=255/bInterfaceSubClass=255/bInterfaceProtocol=255/bNumEndpoints=2
                          - usbserial or hso device name (Linux/macOS): "/dev/tty{USB,HS,other}{0-9}"
                          - COM port identifier (Windows): "COM{0-9}"
                          - "vid:pid[:cfg:intf]" (vendor ID/product ID/optional bConfigurationValue/optional
                            bInterfaceNumber) format in hexa: e.g. "05c6:9091" or "05c6:9091:1:0 (vid and pid
                            are four zero-padded hex digits, cfg and intf are canonical values from the USB
                            descriptor, or guessed using the criteria specified for "auto" above if not specified)
                          - "bus:addr[:cfg:intf]" (USB bus/device address/optional bConfigurationValue/optional
                            bInterfaceNumber) format in decimal: e.g "001:003" or "001:003:0:3" (bus and addr are
                            three zero-padded digits, cfg and intf are canonical values from the USB descriptor)
  --dlf-read DLF_FILE   Read a DLF file generated by QCSuper or QXDM, enabling interoperability with vendor software.
  --json-geo-read JSON_FILE
                        Read a JSON file generated using --json-geo-dump.

Modules:
  Modules writing to a file will append when it already exists, and consider it Gzipped if their name contains ".gz".

  --info                Read generic information about the baseband device.
  --pcap-dump PCAP_FILE
                        Generate a PCAP file containing GSMTAP frames for 2G/3G/4G, to be loaded using Wireshark.
  --wireshark-live      Same as --pcap-dump, but directly spawn a Wireshark instance.
  --memory-dump OUTPUT_DIR
                        Dump the memory of the device (may not or partially work with recent devices).
  --dlf-dump DLF_FILE   Generate a DLF file to be loaded using QCSuper or QXDM, with network protocols logging.
  --json-geo-dump JSON_FILE
                        Generate a JSON file containing both raw log frames and GPS coordinates, for further reprocessing. To be used in combination with --adb.
  --decoded-sibs-dump   Print decoded SIBs to stdout (experimental, requires pycrate).

PCAP generation options:
  To be used along with --pcap-dump or --wireshark-live.

  --reassemble-sibs     Include reassembled UMTS SIBs as supplementary frames, also embedded fragmented in RRC frames.
  --decrypt-nas         Include unencrypted LTE NAS as supplementary frames, also embedded ciphered in RRC frames.
  --include-ip-traffic  Include unframed IP traffic from the UE.

Memory dumping options:
  To be used along with --memory-dump.

  --start MEMORY_START  Offset at which to start to dump memory (hex number), by default 00000000.
  --stop MEMORY_STOP    Offset at which to stop to dump memory (hex number), by default ffffffff.
```

Specifying `-` to pipe data from stdin or towards stdout is supported (gzipped content may not be detected).

### How to root my phone?

This README file is not a guide over how to root your phone (getting your phone to enable you to run commands such as "`su`").

In most of the recent Android devices, you must first use the "OEM/bootloader unlock" option prevent in the developer settings of the telephone in order to unlock the bootloader, then you may use a tool such as [Magisk](https://topjohnwu.github.io/Magisk/install.html) that will enable you to obtain a patched image for your phone's bootloader, that you will then be able to load onto your phone in [`fastboot` mode](https://en.wikipedia.org/wiki/Fastboot).

QCSuper will have more chance to work easily on your Qualcomm-based device when your phone is rooted, but there often are ways to enable the Qualcomm Diag USB mode (also known as "DM", Diag Monitor) on your phone without having your phone rooted. This [depends on](https://band.radio/diag) your phone vendor and goes through, for example, typing a magic combination of digits onto your phone's dialer keypad. Please see the "*How to manually enable the diagnostic ports on my phone?*" section below for more details.

Before rooting your phone, remember that you may also want to use load an alternate recovery image such as TWRP onto your OEM-unlocked phone in order to perform partition backup using a tool such as [TWRP](https://twrp.me/) (it may be as simple as loading the image through Fastboot, enabling the ADB link in the settings of TWRP, and using `adb pull` onto selected partitions in the `/dev/block/by-name` folder`).

For specific inscriptions on rooting or enabling the Diag mode on your phone model, you may search the information over the XDA-developers forum with appropriate keywords.

### How to manually enable the diagnostic ports on my phone?

On Qualcomm/MSM Android-based devices **bearing Linux kernel 4.9 or earlier** (this includes roughly part of devices up to Android 12 and all devices before Android 10), Qualcomm-based Android devices normally **contain a system device called `/dev/diag`** which allows to communicate data to the diagnostics port of the baseband.

On Qualcomm/MSM Android-based devices **bearing Linux kernel 4.14 or later** (this includes roughly part of devices from Android 10 and all devices from Android 13), **`/dev/diag` disappeared**, as the corresponding `diagchar` module is disabled by default recent AOSP/Linux kernels.

On the devices **bearing a Linux 4.9 or earlier MSM kernel**, when using the `--adb` flag, QCSuper will **try to connect through ADB automatically**, will then attempt to transfer an executable utility connecting to the `/dev/diag` device, in order to launch it as root using a command such as `su -c /data/local/tmp/adb_bridge`, and subsequently **transmit the diagnostics data with the device over TCP** (also forwarding the corresponing TCP port through ADB).

On the devices **bearing a Linux 4.14 or later MSM kernel**, when using the `--adb` flag, QCSuper will try to connect through ADB automatically, will then attempt to **mode-switch the USB port** of the phone using a command such as `su -c 'setprop sys.usb.config diag,adb'`, and then execute the **equivalent of the `--usb-modem auto` flag** (see below).

The `--usb-modem <value>` flag allows QCSuper to **connect to the Qualcomm diagnostics port over a pseudo-serial port over USB**, independently from ADB, which is the most common way to connect to the Qualcomm diag protocol of an Android-based phone using an external device.

In order to use `--usb-modem <value>` flag, the Qualcomm diagnostic port must be enabled on the corresponding phone, otherwise said **the phone should have been USB mode-switched** beforehand.

The most common way to USB mode-switch your device is to execute a command such as `setprop sys.usb.config diag,adb` as root, but there may be other ways (with certain phone vendors) to enable the Qualcomm diagnostics-over-USB mode, see for example [this page](https://band.radio/diag) for possible ways, for certain devices, to enable Diag without root - it often imples to type a magic combination of digits over the phone's dialer keypad.

In other devices, it may also be possible to use an APK file signed by the phone vendor and with System-related permissions in order to enable the Diag mode without rooting (search about the `com.longcheertel.midtest` APK for Xiaomi-based devices for example).

Once your device has been correctly most-switched, running the `getprop sys.usb.config` command over ADB should display a text string containing `diag`.

On the side of your computer, then, running `lsusb` (on Linux) should display a line referring your device, for example:

```
Bus 001 Device 076: ID 05c6:9091 Qualcomm, Inc. Intex Aqua Fish & Jolla C Diagnostic Mode
```

Note the `001:076` (bus index/device index identifier), and the `05c6:9091` (vendor ID/product ID) information present in this output.

Once you have this information available, **you may try to use a flag such as `--usb-modem 05c6:9091` or `--usb-modem 001:076`** with QCSuper (please respect the digit padding).

If this isn't conclusive, you may use the `lsusb -v -d 05c6:9091` command, which should produce detailed output, including the USB configurations, interfaces and endpoints for the corresponding USB device:

```
Bus 001 Device 027: ID 05c6:9091 Qualcomm, Inc. Intex Aqua Fish & Jolla C Diagnostic Mode
Device Descriptor:
  bLength                18
  bDescriptorType         1
  bcdUSB               2.01
  bDeviceClass            0 
  bDeviceSubClass         0 
  bDeviceProtocol         0 
  bMaxPacketSize0        64
  idVendor           0x05c6 Qualcomm, Inc.
  idProduct          0x9091 Intex Aqua Fish & Jolla C Diagnostic Mode
  bcdDevice            5.04
  iManufacturer           1 Xiaomi
  iProduct                2 Mi 11
  iSerial                 3 d94f4341
  bNumConfigurations      1
  Configuration Descriptor:
    bLength                 9
    bDescriptorType         2
    wTotalLength       0x0086
    bNumInterfaces          4
    bConfigurationValue     1
    iConfiguration          4 Default composition
    bmAttributes         0x80
      (Bus Powered)
    MaxPower              500mA
    Interface Descriptor:
      bLength                 9
      bDescriptorType         4
      bInterfaceNumber        0
      bAlternateSetting       0
      bNumEndpoints           2
      bInterfaceClass       255 Vendor Specific Class
      bInterfaceSubClass    255 Vendor Specific Subclass
      bInterfaceProtocol     48 
      iInterface              0 
[...]
```

QCSuper allows you to manually select the identifiers of the configuration and the interface you are wishing to attempt to connect to on the concerned device (designated as `bConfigurationValue` and `bInterfaceNumber` in the raw USB descriptor), in the case where it isn't detected correctly. For example, the `--usb-modem 05c6:9091:1:0` flag will select respectively configuration 1 and the interface 0 on the concerned device.  `--usb-modem 05c6:9091:1:4` will select the interface 4 over the configuration 1.

If the configuration and interface indexes detail isn't specified, it will select the first interface descriptor on the system USB bus which is found to match the following criteria, by order of preference:
* `bInterfaceClass=255/bInterfaceSubClass=255/bInterfaceProtocol=48/bNumEndpoints=2`
* `bInterfaceClass=255/bInterfaceSubClass=255/bInterfaceProtocol=255/bNumEndpoints=2`

When using the `--usb-modem auto` flag, the first device exposing an USB interface compilant with this criteria is picked, and if needed on Linux the underlying `/dev/ttyUSB*` (`usbserial` module) or `/dev/ttyHS*` (`hso` module) character device is selected, in the case where the device has been detected and mounted by a kernel module (see the "Using QCSuper with an USB modem" section below).

*Alternately*, on Linux, it may also be possible to manually create `/dev/ttyUSB*` endpoints corresponding to the interfaces of a given USB device, that you will able to can connect using QCSuper with a flag such as `--usb-modem /dev/ttyUSB0` (this may require running QCSuper with root rights), using the `usbserial` module. For this, you can use a command such as:

```
sudo rmmod usbserial
sudo modprobe usbserial vendor=0x05c6 product=0x9091
```


## Using QCSuper with an USB modem

You can use QCSuper with an USB modem exposing a Diag port using the `--usb-modem <device>` option, where `<device>` is the name of the pseudo-serial device on Linux (such as `/dev/ttyUSB0`, `/dev/ttyHS2` and other possibilites) or of the COM port on Windows (such as `COM2`, `COM3`).

Please note that in most setups, you will need to run QCSuper as root in order to be able to use this mode, notably for handling serial port interference.

If you don't know which devices under `/dev` expose the Diag port, you may have to try multiple of these. You can try to auto-detect it by stopping the ModemManager daemon (`sudo systemctl stop ModemManager`), and using the following command: `sudo ModemManager --debug 2>&1 | grep -i 'port is QCDM-capable'` then Ctrl-C.

Please note that if you're not able to use your device with for example ModemManager in the first place, it is likely that it is not totally setup and that it will not work neither with QCSuper. A few possible gotchas are:

  * You didn't apply the proper [mode switching](https://wiki.archlinux.org/index.php/USB_3G_Modem#Mode_switching) command for your device.
  
  * If you bought a device that previously had a SIM from a different operator, your device may be sim-locked. You may have to use the unlock code from the former operator and submit it to the device, as if it was a PIN code: `sudo mmcli -i 0 --pin=<your_unlock_code>`

If your Qualcomm-based USB device doesn't expose a Diag port by default, you may need to type the following through the AT port in order to enable the Diag port:

```
AT$QCDMG
```

Please note that only one client may communicate with the Diag port at the same time. This applies to two QCSuper instances, or QCSuper and ModemManager instances.

If ModemManager is active on your system, QCSuper will attempt to dynamically add an udev rule to prevent it to access the Diag port and restart its daemon, as it's currently the best way to achieve this. It will suppress this rule when closed.

## Supported devices

QCSuper was successfully tested with:

* Sony Xperia Z (Phone) - 4G - works out of the box after rooting an enabling adb
* Nexus 6P (Phone) - 4G - works out of the box after rooting an enabling adb
* ZTE MF823 (USB Modem) - 4G - may require to [mode-switch the device to CDC-WDM](https://wiki.archlinux.org/index.php/ZTE_MF_823_%28Megafon_M100-3%29_4G_Modem#Device_Identification), set the device to [factory mode](https://wiki.archlinux.org/index.php/ZTE_MF_823_%28Megafon_M100-3%29_4G_Modem#Commands), then execute the AT command mentioned above
* ZTE MF667 (USB Modem) - 3G, 2011 - should work out of the box (may require mode switching)
* Option Icon 225 (USB Modem) - 3G, 2008
* Novatel Ovation MC998D (USB Modem)
* ZTE WCDMA Technologies MSM MF110/MF627/MF636 (USB Modem)
* ZTE 403zt (USB Modem) - 4G
* OnePlus One and 3 (Phones)
* Andromax A16C3H (Phone)
* Samsung Galaxy S4 GT-I9505 (Phone)

Is it however aiming to be compatible with the widest possible range of devices based on a Qualcomm chipset, for the capture part.

Do no hesitate to report whether your device is successfully working or not through opening a [Github issue](https://github.com/P1sec/QCSuper/issues/new).

## Related tools using the Diag protocol

There are a few other open tools implementing bits of the Diag protocol, serving various purposes:

* [ModemManager](https://github.com/endlessm/ModemManager): the principal daemon enabling to use USB modems on Linux, implements bits of the Diag protocol (labelled as QCDM) in order to retrieve basic information about USB modem devices.
* [SnoopSnitch](https://opensource.srlabs.de/projects/snoopsnitch) (specifically [gsm-parser](https://github.com/E3V3A/gsm-parser)): chiefly an Android application whose purpose is to detect potential attacks on the radio layer (IMSI catcher, fake BTS...). It also have a secondary feature to capture some signalling traffic to PCAP, which does not provide exactly the same thing as QCSuper (LTE traffic isn't encapsulated in GSMTAP for example, device support may be different).
  * [diag-parser](https://github.com/moiji-mobile/diag-parser): A Linux tool that derivates from the PCAP generation feature from SnoopSnitch, somewhat improved, designed to work with USB modems.
* [MobileInsight](http://www.mobileinsight.net/): this Android application intends to parse all kinds of logs output by Qualcomm and Mediatek devices (not only those containing signalling information, but also proprietary debugging structures), and dumping these to a specific XML representation format. Does not provide user-facing PCAPs (but formerly used Wireshark as a backend for converting certain protocol information to XML).
* [qcombbdbg](https://code.google.com/archive/p/qcombbdbg/): A debugger for the Qualcomm baseband setting up itself by hooking a Diag command, through using the Diag command that allows to write to memory, for the Option Icon 225 USB modem.
* [OpenPST](https://github.com/openpst/openpst): A set of tools related to Qualcomm devices, including a GUI utility allowing, for example, to read data on the tiny embedded filesystem accessible through Diag (EFS).
* [SCAT](https://github.com/fgsect/scat): A tool with similar GSMTAP generation abilities, taking as input a serial port, also supporting Samsung Exynos.
