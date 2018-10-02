QCSuper can be split up into two building blocks:

* **Inputs** are Python classes exposing interfaces to read and optionally send Diag protocol data. We can distinguish:
  * Inputs for communicating live with devices (the `--adb` input for talking with rooted Android phones, the `--usb-modem` for talking with USB modems)
  * Inputs for processing saved data (`--dlf-read` is able to read data in a format providing interoperability with the vendor QXDM tool)

* **Modules** are Python classes using inputs to perform specific tasks using the Diag protocol. For example:
  * Capturing raw 2G/3G/4G signalling traffic (`--pcap-dump` will dump to a PCAP file, `--wireshark-live` will open directly Wireshark)
  * Gathering generation info about the device (`--info`)
  * Capturing raw Diag logs information into reusable formats (`--json-geo-dump`, `--dlf-dump`)

## Internal architecture

QCSuper needs to deal to multiple sources of input:

* The connected Diag device
  * Which can be different kinds of descriptor:
    * A pseudo-serial USB device
    * A TCP socket communicating with a remote Android device
    * A file to replay from
  * Which can deliver different kinds of received data:
    * Synchronous responses to requests
    * Asynchronous logs or messages (see [The Diag protocol.md](The%20Diag%20protocol.md))
  * When the source is a real device, the device can accept only one Diag client at once

* An optional interactive prompt (`--cli` module): needed to provide a handy way to continue capturing on the Diag client while executing other tasks

All this requires a form of concurrency to be acheived: either threading, or a way to poll on descriptors through an event loop.

The design ease/simplicity tradeoff I have chosen was to use threading (but I'm open to rework the architecture if someone has something else to propose). Polling on both a serial port and a featureful command prompt or thread queue (for example) is not doable easily in a multi-platform way, and using asyncio seemed to add some design and syntaxic overhead/external libraries to the equation.

### Threading model

QCSuper makes use of different threads:

* The main thread contains the loop reading from the device, and is the only place where reading is performed (it will also dispatch asynchronous messages to modules, calling the `on_log`, `on_message` which may not write neither read, and call at teardown the `on_deinit` callback with may write)
* A background thread is used for initializing the modules selected through command line arguments (calling the `on_init` callback which may write)
* A background thread may be used for the optional interactive prompt (`--cli`) and initializing the modules called from it (calling the `on_init` callback which may write)

### Modules API

A module is a Python class which may expose different methods:

* `__init__`: will receive the input object as its first argument, and optionally other arguments from the command line or interactive prompt (passed in sequence from the entry point `qcsuper.py`).
* `on_init`: called when the connection to the Diag device was established. Not called when the input is not a device but a file containing recorded log data.
* Callbacks triggered by a read on the input source:
  * `on_log`: called when an asynchronous response Diag protocol raw "log" was received.
  * `on_message`: called when an asynchronous response Diag protocol text "message" structure was received.
* `on_deinit`: called when the connection to the Diag device ceased establishment, or the user hit Ctrl+C.

The methods composing these callback may perform request-response operations (using `self.diag_reader.send_recv(opcode, payload)`, where `self.diag_reader` is the input object).

When a request-response operation is performed, the thread for the callback is paused using the response is received, using a thread synchronization primitive shared with the main thread.

When using the interactive prompt (`--cli`), the moment where the `on_init` callbacks ends is the moment where the used is informed that the task continued to background (or is finished, in the case where there is no further callbacks).

### Inputs API

A module is a Python class which may expose different methods:

* `__init__`: will optionally receive arguments from the command line or interactive prompt (passed in sequence from the entry point `qcsuper.py`).
* `send_request`: this function will be called when a module wants to send a Diag request packet.
* `read_loop`: Diag responses packets will be read and dispatched from here.

Inputs inherit from the `BaseInput` class which exposes a method called `send_recv`, allowing to write a request then read the response, wrapping transparently thread synchronization primitives.

`send_recv` is most likely the only method of an input to be called directly from a module.
