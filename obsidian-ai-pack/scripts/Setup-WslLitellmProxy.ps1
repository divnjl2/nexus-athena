<#
.SYNOPSIS
  HOME-ONLY fallback. Exposes a WSL-hosted litellm to Windows when WSL2
  localhostForwarding is OFF.

.DESCRIPTION
  In most setups you do NOT need this: WSL2 forwards a service bound to 127.0.0.1
  inside WSL to 127.0.0.1 on Windows (loopback, firewall-exempt). So just run
  `Install-ObsidianAI.ps1 -Backend local` and the default endpoint
  http://127.0.0.1:8413/v1 reaches the WSL litellm directly.

  Use THIS only if 127.0.0.1:8413 is NOT reachable from Windows. It starts a socat
  sidecar inside WSL (as a transient systemd unit, surviving the WSL session) on
  0.0.0.0:<BridgePort> -> 127.0.0.1:<LitellmPort>, then prints the WSL-IP endpoint.
  A non-loopback WSL-IP endpoint also needs an outbound firewall allow rule on
  Windows if you run a default-deny outbound policy. The WSL IP changes on reboot -
  re-run after a reboot to refresh.

.PARAMETER LitellmPort  Port litellm listens on inside WSL (loopback). Default 8413.
.PARAMETER BridgePort   Port the sidecar exposes on the WSL IP. Default 8414.

.EXAMPLE
  $u = .\scripts\Setup-WslLitellmProxy.ps1 | Select-Object -Last 1
  .\Install-ObsidianAI.ps1 -Backend custom -Endpoint $u -ApiKey <litellm-master-key> -Model qwopus-9b
#>
[CmdletBinding()]
param(
  [int]$LitellmPort = 8413,
  [int]$BridgePort  = 8414
)
$ErrorActionPreference = 'Stop'

# Single-quoted here-string: PowerShell does NOT touch $VAR / $(...) here, so the bash
# is delivered verbatim. Only the two numeric ports are substituted via .Replace().
# NOTE: systemd-run kept on ONE line (no '\' continuation) and CRLF normalized to LF
# below, because this string is delivered to `bash -lc` where a '\'+CR breaks the line
# continuation and trailing CRs cause "unexpected end of file".
$bash = (@'
set -e
LP=__LP__; BP=__BP__
systemctl stop obsidian-litellm-bridge.service 2>/dev/null || true
systemctl reset-failed obsidian-litellm-bridge.service 2>/dev/null || true
pkill -f "TCP-LISTEN:$BP" 2>/dev/null || true
SOCAT=$(command -v socat || true)
if [ -z "$SOCAT" ]; then echo "ERROR: socat not installed in WSL (apt-get install socat)"; exit 1; fi
systemd-run --unit=obsidian-litellm-bridge --service-type=simple "$SOCAT" TCP-LISTEN:$BP,bind=0.0.0.0,fork,reuseaddr TCP:127.0.0.1:$LP >/dev/null 2>&1
sleep 2
systemctl is-active obsidian-litellm-bridge.service >/dev/null 2>&1 || { echo "ERROR: bridge unit not active"; exit 1; }
hostname -I | awk '{print $1}'
'@).Replace('__LP__', "$LitellmPort").Replace('__BP__', "$BridgePort").Replace("`r`n", "`n")

# Pass the script base64-encoded: a single argv token with no quoting/newline/CRLF
# pitfalls. bash decodes and executes it. This is the robust way to run a multi-line
# script in WSL from PowerShell.
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
$out = & wsl.exe -e bash -lc "echo $b64 | base64 -d | bash" 2>&1
$wslip = ($out | Select-Object -Last 1).ToString().Trim()
if ($wslip -notmatch '^\d+\.\d+\.\d+\.\d+$') {
  throw "Bridge setup failed: $out"
}
$endpoint = "http://$wslip`:$BridgePort/v1"
Write-Host "[+] WSL litellm bridge up (systemd unit): 0.0.0.0:$BridgePort -> 127.0.0.1:$LitellmPort (WSL $wslip)"
Write-Host "[i] Endpoint for the installer (-Endpoint):"
Write-Output $endpoint
