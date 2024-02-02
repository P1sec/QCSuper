from logging import error, warning, info, debug
import os, socket, struct
from pathlib import Path
from subprocess import Popen
from typing import Any

from .adb import AdbConnector

class AdbWsl2Connector:
    """
    AdbWsl2Connector implement the BaseInput Interface/Protocol at runtime by proxyfying calls to an AdbConnector instance.
    """

    def __init__(self, adb_exe: str) -> None:
        self._disposed = False
        self._wsl_distro_name = os.environ.get('WSL_DISTRO_NAME', '')
        if not self._wsl_distro_name:
            error('WSL_DISTRO_NAME does not exists, are you using WSL2?')
            exit()

        bridge_ctrl_path = (Path(__file__).parent / 'adb_wsl2_bridge' / 'adb_wsl2_bridge.ps1').resolve()
        self._win_bridge_ctr_path = f'\\\\wsl$'
        for idx, part in enumerate(bridge_ctrl_path.parts):
            if idx == 0:
                self._win_bridge_ctr_path += f'\\{self._wsl_distro_name}'
                continue
            self._win_bridge_ctr_path += f'\\{part}'
        
        res = self._up()
        if res != 0:
            error(f'Could not successfully setup adb wsl2 bridge: {res}') 
            exit()
        self._connector = AdbConnector(adb_exe=adb_exe, adb_host=self._default_gw())

    def _default_gw(self) -> str:
        """
        Return WSL2 default network gateway as string repr
        """
        with open('/proc/net/route') as fd:
            for line in fd:
                fields = line.strip().split()
                if len(fields) < 4 or fields[1] != '00000000' or not int(fields[3], 16) & 2:
                    continue
                raw_default_gw = int(fields[2], 16)
                return socket.inet_ntoa(struct.pack('<L', raw_default_gw))

        raise RuntimeError("Could not found the ip route default gateway")

    def _up(self) -> int:
        """
        Call powershell script via WSL2/Windows interropability to setup the networking
        for QCSuper ADB bridge communication:
            - Open QCSuper port access in Windows Firewall
            - Add QCSuper required Windows portproxy rule
        """
        p = Popen([
            'powershell.exe',
            '-WindowStyle',
            'Hidden',
            '-c', 
            f'Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force; Start-Process powershell -WindowStyle Hidden -Wait -PassThru -ArgumentList "-F `"{self._win_bridge_ctr_path}`" `"{self._wsl_distro_name}`" up" | Out-Null'
        ])
        res = p.wait()
        return res

    def _down(self) -> int:
        """
        Call powershell script via WSL2/Windows interropability to tear down the networking
        for QCSuper ADB bridge communication
            - Close QCSuper port access in Windows Firewal
            - Remove QCSuper Windows portproxy rule
        """
        p = Popen([
            'powershell.exe', 
            '-WindowStyle',
            'Hidden',
            '-c', 
            f'Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force; Start-Process powershell -WindowStyle Hidden -Wait -PassThru -ArgumentList "-F `"{self._win_bridge_ctr_path}`" `"{self._wsl_distro_name}`" down" | Out-Null'
        ])
        res = p.wait()
        return res

    def dispose(self, disposing: bool = True) -> None:
        if self._disposed:
            return

        try:
            if self._connector:
                self._connector.dispose()

            res = self._down()
            if res != 0:
                error(f'Could not successfully teardown adb wsl2 bridge: {res}')
            else:
                self._disposed = True
        except Exception as e:
            error(f'Could not successfully teardown adb wsl2 bridge << {e}')

    def __setattr__(self, name: str, value: Any) -> None:
        """
            Proxify setter to unerlaying ADB connector if needed
        """
        if name not in [
            '_wsl_distro_name',
            '_win_bridge_ctr_path',
            '_connector',
            '_disposed'
        ]:
            self._connector.__setattr__(name, value)
        else:
            super().__setattr__(name, value)

    def __getattribute__(self, name: str) -> Any:
        """
            Proxify getter to underlaying ADB connector if needed
        """
        if name not in [
            '_wsl_distro_name',
            '_win_bridge_ctr_path',
            '_disposed',
            '_connector',
            'dispose',
            '_up',
            '_down',
            '_default_gw'
        ]:
            return self._connector.__getattribute__(name)
        else:
            return super().__getattribute__(name)
        