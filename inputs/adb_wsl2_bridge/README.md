# ADB WSL2 Bridge
This directory contains a PowerShell script to setup/teardown the required networking configuration to access `QCSuper` ADB bridge from a WSL2 instance.

It is use by QCSuper `--wsl2-adb` connector that leverage WSL2/Windows interoperability.

```
                      ┌─────────────────────────────────┐
                      │                                 │
                      │                 Windows         │
┌─────────────┐       ├───────────────┐  running ADB    │
│             │       │               │                 │
│             ├───────►vEthernet(WSL) │                 │
│     WSL2    │       │               │                 │
│             │       ├───────┬───────┘                 │
│             │       │       │                         │
└─────────────┘       │       │                         │
                      │  ┌────▼──────┐                  │
                      │  │ Localhost │                  │
                      └──┴────┬──────┴──────────────────┘
                              │
                          ┌───▼────────────────┐
                          │                    │
                          │ QCSuper ADB Bridge │
                          ├────────────────────┤
                          │                    │
                          │         UE         │
                          │                    │
                          └────────────────────┘
```

## Usage
```
> .\adb_wsl2_bridge.ps1
Usage: \adb_wsl2_bridge.ps1 wsl2-distro-name [up|down]
```

### Up
- Open QCSuper port in Windows Firewall
- Forward traffic send to WSL2 gateway (vEthernet-WSL) to Windows locathost when the target port is QCSuper ADB bridge

### Down
- Close QCSuper port in Windows Firewall
- Remove traffic forwarding rules created for QCSuper


## QCSuper usage sample
```
$ ./qcsuper.py --adb-wsl2=/mnt/d/Android/SDK/platform-tools/adb.exe --info
logging switched

[+] Compilation date:    Sep  6 2019 14:32:56
[+] Release date:        Feb 27 2019 03:00:00
[+] Version directory:   sdm660.g

[+] Common air interface information:
[+]   Station classmark: 58
[+]   Common air interface revision: 9
[+]   Mobile model:      255
[+]   Mobile firmware revision: 100
[+]   Slot cycle index:  48
[+]   Hardware revision: 0x08c (0.140)

[+] Mobile model ID:     0xXXX
[+] Chip version:        0
[+] Firmware build ID:   MPSSXXXXXX

[+] Diag version:        8

[+] Serial number:       XXXXXXXXXX
```

