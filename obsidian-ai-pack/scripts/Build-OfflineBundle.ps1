<#
.SYNOPSIS
  Build the self-contained OFFLINE bundle ZIP for locked-down office machines.

.DESCRIPTION
  Run this AT HOME (where GitHub is reachable). It fetches the pinned plugin builds
  and zips everything a locked-down machine needs - Install.bat (double-click),
  the installer, the plugins, MANUAL-INSTALL.txt, README - into one ZIP. Carry the
  ZIP to the office (USB / email / cloud), extract, double-click Install.bat (or
  follow MANUAL-INSTALL.txt). No git, no gh, no internet needed at the office, only
  access to your chosen model endpoint.

.PARAMETER OutZip  Output path. Default: <pack>\dist\obsidian-ai-pack-offline.zip
#>
[CmdletBinding()]
param([string]$OutZip)
$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackDir   = Split-Path -Parent $ScriptDir
if (-not $OutZip) { $OutZip = Join-Path $PackDir 'dist\obsidian-ai-pack-offline.zip' }

# 1. fetch plugin builds into <pack>\plugins
& (Join-Path $ScriptDir 'Fetch-Plugins.ps1') -Dest (Join-Path $PackDir 'plugins')

# 2. stage everything the offline bundle ships
$stage = Join-Path ([System.IO.Path]::GetTempPath()) ("oaip_" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $stage | Out-Null
$ship = @('Install.bat','Install-ObsidianAI.ps1','MANUAL-INSTALL.txt','README.md','plugins','config-templates','scripts')
foreach ($item in $ship) {
  $src = Join-Path $PackDir $item
  if (Test-Path $src) { Copy-Item -Recurse -Force $src (Join-Path $stage (Split-Path $item -Leaf)) }
}

# 3. zip
New-Item -ItemType Directory -Force -Path (Split-Path $OutZip) | Out-Null
if (Test-Path $OutZip) { Remove-Item $OutZip -Force }
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $OutZip
Remove-Item -Recurse -Force $stage

$mb = [math]::Round((Get-Item $OutZip).Length / 1MB, 1)
Write-Host "[+] offline bundle: $OutZip ($mb MB)"
Write-Host "    Carry it to the office -> extract -> double-click Install.bat (or read MANUAL-INSTALL.txt)."
