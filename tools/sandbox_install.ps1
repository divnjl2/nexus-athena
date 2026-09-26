# One-time host preparation for `athena dispatch --sandbox on|required` on Windows (foundry C-10.1).
# Pure ASCII on purpose (RU-locale PowerShell decodes .ps1 as cp1251).
#
# What the sandbox is: sandbox-runtime (srt) runs the executor as the local account `srt-sandbox`
# with a WFP egress fence (loopback only inside the proxy port range, where the fenced relays listen)
# and NTFS ACEs. Measured 26.09.2026 on win-desktop, the reasons for each step below:
#   - CreateProcessWithLogonW failed with 0x80070005 until the sandbox account could READ the srt
#     package (a per-user npm install under the caller's profile is invisible to another account).
#   - srt-win's per-run ACL stamp has a fixed 60 s budget and Windows walks the whole subtree when
#     an inheritable ACE lands, so the big toolchain trees are granted ONCE here, never per run.
#   - node's realpath lstats every ancestor of a per-user install, so pi runs from a machine-wide
#     copy under ProgramData instead of the caller's profile.
#   - the D: drive grants Authenticated Users modify, so the sandbox account could write anywhere
#     on it: the lane, model and secret trees get a persistent deny (the worktrees stay on D:).
#   - the sandbox drops the environment and does not forward stdin: the dispatcher writes a launcher
#     and the packet into <worktree>/.athena and seeds pi's agent directory from $SeedDir.
# Reverse any grant with: icacls <path> /remove:g <sid>   and a deny with: icacls <path> /remove:d <sid>
param(
  [string]$PythonDir = (Split-Path (Split-Path (Get-Command python).Source)),
  [string]$NpmDir = (Split-Path (Get-Command srt.cmd).Source),
  [string]$SeedDir = (Join-Path $env:USERPROFILE '.athena\sandbox\pi-agent'),
  [string]$SeedModelsFrom = 'D:\llm-lanes\pi-agent\models.json',
  [string[]]$DenyWrite = @('D:\llama-swap','D:\llm-lanes','D:\models','D:\vllm-win','D:\vllm-win-021','D:\vllm-win-022','D:\secrets','D:\.backup-keys','D:\nexus-models','D:\hf_cache'),
  [string]$ProgramDataPi = 'C:\ProgramData\athena\npm',
  [switch]$SkipPiInstall
)
$ErrorActionPreference = 'Stop'
$user = Get-LocalUser -Name 'srt-sandbox' -ErrorAction SilentlyContinue
if (-not $user) { throw 'srt-sandbox account missing: run  npx @anthropic-ai/sandbox-runtime windows-install  first (one UAC prompt)' }
$sid = '*' + $user.SID.Value
Write-Output "sandbox account $($user.SID.Value)"

# 1. reads on the toolchain trees, once (minutes on a big Python tree; icacls prints the count)
foreach ($d in @($NpmDir, $PythonDir)) {
  if (Test-Path $d) { Write-Output "grant RX $d"; icacls $d /grant "${sid}:(OI)(CI)RX" /T /Q | Select-Object -Last 1 }
}

# 2. the machine-wide pi the sandboxed executor runs (same version as the caller's)
if (-not $SkipPiInstall) {
  $v = (npm ls -g @mariozechner/pi-coding-agent --depth=0 2>$null | Select-String -Pattern 'pi-coding-agent@([0-9.]+)').Matches | ForEach-Object { $_.Groups[1].Value } | Select-Object -First 1
  if (-not $v) { $v = 'latest' }
  New-Item -ItemType Directory -Force $ProgramDataPi | Out-Null
  Write-Output "npm install -g --prefix $ProgramDataPi @mariozechner/pi-coding-agent@$v"
  npm install -g --prefix $ProgramDataPi "@mariozechner/pi-coding-agent@$v" | Select-Object -Last 2
}

# 3. the seed of pi's per-run agent directory: relay-only providers, no package installs
New-Item -ItemType Directory -Force $SeedDir | Out-Null
if (Test-Path $SeedModelsFrom) { Copy-Item $SeedModelsFrom (Join-Path $SeedDir 'models.json') -Force }
else { Write-Warning "no $SeedModelsFrom : put a models.json naming only the fenced relays into $SeedDir" }
$settings = @{ compaction = @{ enabled = $true; reserveTokens = 6144; keepRecentTokens = 12288 }; retry = @{ enabled = $true; maxRetries = 2; baseDelayMs = 2000 } }
$settings | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $SeedDir 'settings.json') -Encoding utf8
Write-Output "seed directory $SeedDir"

# 4. persistent write denies on the world-writable trees the executor must never touch
foreach ($d in $DenyWrite) {
  if (Test-Path $d) { Write-Output "deny W $d"; icacls $d /deny "${sid}:(OI)(CI)W" /T /Q | Select-Object -Last 1 }
}

# 5. smoke: the spawn, from a directory on the worktrees' drive
$probe = Join-Path 'D:\tmp' ('athena-sandbox-probe-' + [guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Force $probe | Out-Null
Set-Location $probe
$cfg = @{ network = @{ allowedDomains = @('127.0.0.1:60081','localhost:60081'); deniedDomains = @(); allowLocalBinding = $false }
          filesystem = @{ denyRead = @(); allowRead = @($probe); allowWrite = @($probe); denyWrite = @() }
          windows = @{ proxyPortRange = @(60080, 60089) } }
$cfg | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $probe 'settings.json') -Encoding utf8
& srt --settings (Join-Path $probe 'settings.json') -c 'cmd /c whoami'
Write-Output 'done: the line above must read desktop\srt-sandbox'
