# WSL2 network configuration for QCSuper ADB bridge access from WSL2
# - Open/Close port in windows Firewall
# - Open/Close port TCP forwarding from WSL2 GW to Windows localhost

If ($Args.Count -lt 2 -or (-Not $Args[1] -eq "up" -and -Not $Args[1] -eq "down")) {
    $CmdPath = $MyInvocation.MyCommand.Path
    echo "Usage: $CmdPath wsl2-distro-name [up|down]" ;
    exit 1;
}

$QCSuperPort = (43555);
$WSLDistribName = $Args[0];
$Action = $Args[1];
$WSLGateway = '';

# Escalate priviledges if needed
If (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))
{
  $WSLGatewayJSON = wsl -d "$WSLDistribName" ip --json r get 1.1.1.1;
  $WSLGateway = ($WSLGatewayJSON | ConvertFrom-Json).gateway;
  $TempFile = (New-TemporaryFile).FullName + '.ps1';

  Copy-Item -Path $MyInvocation.MyCommand.Path -Destination $TempFile;
  Start-Process powershell -Wait -WindowStyle Hidden -PassThru -Verb runas -ArgumentList "-c Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force ; Start-Process powershell -Wait -PassThru -ArgumentList \`"$TempFile $WSLDistribName $Action $WSLGateway\`";";
  Remove-Item $Tempfile;
  
  exit;
}

If ($Args.Count -eq 3) { # After escalating privileges, if we impersonating an other user, we won't have access to wsl anymorel WSL gw is passing through arguments.
  $WSLGateway = $Args[2];
}
else { # CurrentUser already have Administrator priviledges
  echo "[Warning] Your current local Windows user is an Administrator, considere using a Standard user for daily drive!";
  $WSLGatewayJSON = wsl -d "$WSLDistribName" ip --json r get 1.1.1.1;
  $WSLGateway = ($WSLGatewayJSON | ConvertFrom-Json).gateway;
}

if ($Action -eq "up") {
  echo "[+] Creating QCSuper Windows Firewall rules";
  New-NetFireWallRule -DisplayName 'WSL 2 Firewall QCSuper Forwarding' -Direction Outbound -LocalPort $QCSuperPort -Action Allow -Protocol TCP;
  New-NetFireWallRule -DisplayName 'WSL 2 Firewall QCSuper Forwarding' -Direction Inbound -LocalPort $QCSuperPort -Action Allow -Protocol TCP;

  echo "[+] Creating WSL2 port forwarding (fron $WSLGateway : $QCSuperPort to localhost : $QCSuperPort)";
  iex "netsh interface portproxy add v4tov4 listenaddress=$WSLGateway listenport=$QCSuperPort connectaddress=127.0.0.1 connectport=$QCSuperPort | Out-Null";
}

if ($Action -eq "down") {
  echo "[+] Deleting QCSuper Windows Firewall rules";
  while (Remove-NetFireWallRule -DisplayName 'WSL 2 Firewall QCSuper Forwarding') {};

  echo "[+] Deleting WSL2 port forwarding";
  iex "netsh interface portproxy delete v4tov4 listenaddress=$WSLGateway listenport=$QCSuperPort | Out-Null";
}

sleep 1;