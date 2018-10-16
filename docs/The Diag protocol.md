The **Diag protocol**, also called **QCDM** or **DM** (Diagnostic monitor) is a protocol present on Qualcomm-based phones and USB modems.

It can be accessed through multiple channels:

* On Android phones, it is exposed internally through the `/dev/diag` device, created by the "diagchar" kernel module. This device may communicate with the baseband in multiple ways (shared memory, serial).

* On USB modems, it is exposed externally through an USB pseudo-serial port (likely `/dev/ttyUSB*` or `/dev/ttyHSO*`).
  * Most often exposed directly, or requires to send a special AT command (`AT$QCDMG`).
  * This interface can also be often exposed on Android phones, but seems to require to be enabled through a vendor-specific way.

`/dev/diag` should allow to exchange the same data as with the port exposed by USB modems, with some extra framing and IOCTL required.

# The diag protocol over USB

In its simplest form, the Diag protocol uses a simple framing (inspired by the [https://en.wikipedia.org/wiki/High-Level_Data_Link_Control](https://en.wikipedia.org/wiki/High-Level_Data_Link_Control) with less fields).

It is composed of:

* Contents in which the trailer character `\x7e` is escaped as `\x7d\x5e`, and `\x7d` escaped as `\x7d\x5d`:
  * 1 byte: command code
  * n bytes: packet payload
  * 2 bytes: CCITT CRC-16 checksum (with Python: `crcmod.mkCrcFun(0x11021, initCrc=0, xorOut=0xffff)`)
* 1 byte: trailer character (`\x7e`)

Looking at the effective contents, these are composed of two parts, the one-byte command code and the payload that ensues.

Diag is a very feature-rich protocol (even though it is locked down on some recent devices) and exposes a lot of commands. These can be found in certain Internet-facing source code (look for `diagcmd.h`).

We can break down Diag packets sent over the wire into a few kinds:
* Request packets
* Response packets
  * Synchronous responses: will bear the same command code as the request, or an error command code (`DIAG_BAD_CMD_F`, `DIAG_BAD_PARM_F`...).
  * Asynchronous **log packets** (`DIAG_LOG_F`): they contain an encoded raw structure of data, logged by the baseband at some point. Most often proprietary structures, but some packets also expose the raw over-the-air data.
  * Asynchronous **message packets** (`DIAG_MSG_F`, `DIAG_EXT_MSG_F`, `DIAG_EXT_MSG_TERSE_F`): they contain a string of information (debug, error, info...). Composed of a format string and a variable number of arguments.

Diag may expose a lot of functionalites, including:
* Gathering generation information about the device (baseband firmware version, model, serial number...)
* Reading/writing memory (fully enabled on older devices, most often restricted to ranges or disabled on newer)
* Reading/writing non-volatile memory (read and alter protocol-specific state variables)
* Commands related to calls and messaging
* Commands related to GPS
* Commands specific to 2G/3G/4G protocols, layer 1 to 3
* Commands related to the tiny internal filesystem of the baseband (EFS)
* Many more. Most features added after some point in the expansion of Diag use the `DIAG_SUBSYS_CMD_F` command which allows to use a 1-byte subsystem number, followed by a 2-bytes subsystem command code.

# The diag protocol over `/dev/diag`

On Android devices, you can communicate with `/dev/diag` using the following steps:

* Open `/dev/diag` read/write (most often requires root rights)
* Trigger the `DIAG_IOCTL_SWITCH_LOGGING` IOCTL as depicted below (will enable reading/writing Diag frames):

```c
    const unsigned long DIAG_IOCTL_SWITCH_LOGGING = 7;
    const int MEMORY_DEVICE_MODE = 2;
    
    const int mode_param[] = { MEMORY_DEVICE_MODE, -1, 0 }; // diag_logging_mode_param_t

    if(ioctl(diag_fd, DIAG_IOCTL_SWITCH_LOGGING, MEMORY_DEVICE_MODE, 0, 0, 0) < 0 &&
       ioctl(diag_fd, DIAG_IOCTL_SWITCH_LOGGING, &mode_param, sizeof(mode_param), 0, 0, 0, 0) < 0) {
        error("ioctl");
    }
```

* Trigger the `DIAG_IOCTL_REMOTE_DEV` IOCTL which will enable you to know whether you should consider an extra field when reading/writing Diag frames:

```c
    const unsigned long DIAG_IOCTL_REMOTE_DEV = 32;
    int use_mdm = 0;

    if(ioctl(diag_fd, DIAG_IOCTL_REMOTE_DEV, &use_mdm) < 0) {
        error("ioctl");
    }
```

You can now read/write on the character device. Everything is little-endian. The format for writing requests is:

```c
    struct request {
        int data_type; // USER_SPACE_DATA_TYPE = 32
        int device_type; // MDM = -1 (only if use_mdm returned by the ioctl above is 1, or field not present)
        
        char payload[]; // Same framing as with the "diag protocol over USB" described above
    };
```

The format for reading responses is:

```c
    struct response {
        int data_type; // USER_SPACE_DATA_TYPE = 32
        int device_type; // MDM = -1 (only if use_mdm returned by the ioctl above is 1, or field not present)
        
        int nb_buffers; // Number of entries in the field below
        struct response_buffer response_buffers[nb_buffers];
    };
    
    struct response_buffer {
        int buffer_size; // Size in bytes of the field below
        char payload[buffer_size]; // Same framing as with the "diag protocol over USB" described above;
    };
```

# Implementations of the Diag protocol

There exists a vendor Windows client provided by Qualcomm, called QXDM (Extensible Diagnostic Monitor), which can trigger almost all functionality of Diag. It can't however perform the specific tasks QCSuper was designed for (generate a standard PCAP, dump all the device's memory...).

QXDM can save logs received through diag (see the definition of "log packet" above) into a very simple format, consisting of part of the raw Diag packets data, called DLF.

Recent versions use a way more complex format called ISF. Otherwise, they expose options to convert ISF to DLF and the other way around.

QCSuper can both save raw logs into the DLF format, providing interoperability (module --dlf-dump) and reprocess them (input --dlf-read).

There are also a few open source tools implementing bits of the Diag protocol, see the "related tools" section of the README.


