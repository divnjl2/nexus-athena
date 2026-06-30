<#
.SYNOPSIS
  Pre-download the version-pinned plugin builds for an OFFLINE install.

.DESCRIPTION
  Downloads Smart Composer + Copilot (manifest.json, main.js, styles.css) from their
  official GitHub releases into <Dest>\<plugin-id>\. Use gh CLI if present, else
  Invoke-WebRequest. Then transfer <Dest> to an offline machine and run:
    Install-ObsidianAI.ps1 -OfflineDir <Dest> ...
  Plugin builds are NOT committed to this repo (they carry the vendor's own embedded
  OAuth client ids, which trip GitHub push protection, and they bloat the repo).

.PARAMETER Dest  Output folder. Default: .\plugins next to the pack root.

.EXAMPLE
  .\scripts\Fetch-Plugins.ps1 -Dest .\plugins
#>
[CmdletBinding()]
param([string]$Dest)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Dest) { $Dest = Join-Path (Split-Path -Parent $ScriptDir) 'plugins' }

$PluginSpec = @{
  'smart-composer' = @{ repo = 'glowingjade/obsidian-smart-composer'; version = '1.2.9' }
  'copilot'        = @{ repo = 'logancyang/obsidian-copilot';        version = '3.2.8' }
}
$Files = @('manifest.json','main.js','styles.css')
$hasGh = [bool](Get-Command gh -ErrorAction SilentlyContinue)

foreach ($id in $PluginSpec.Keys) {
  $repo = $PluginSpec[$id].repo; $ver = $PluginSpec[$id].version
  $dir = Join-Path $Dest $id
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  foreach ($f in $Files) {
    $out = Join-Path $dir $f; $ok = $false
    if ($hasGh) {
      & gh release download $ver -R $repo -p $f -D $dir --clobber 2>$null
      $ok = ($LASTEXITCODE -eq 0 -and (Test-Path $out))
    }
    if (-not $ok) {
      $url = "https://github.com/$repo/releases/download/$ver/$f"
      try { Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing -ErrorAction Stop; $ok = $true } catch { $ok = $false }
    }
    if (-not $ok) { throw "Failed to fetch $id/$f ($repo @ $ver)." }
  }
  Write-Host "[+] fetched $id ($ver) -> $dir"
}
Write-Host ""
Write-Host "Offline bundle ready at: $Dest"
Write-Host "Install with: .\Install-ObsidianAI.ps1 -OfflineDir '$Dest' -Backend <local|claude|custom> ..."
