<#
.SYNOPSIS
  One-click installer: puts the Smart Composer + Copilot AI-chat plugins into an
  Obsidian vault and pre-wires them to a model backend (local swarm / Claude / any
  OpenAI-compatible endpoint).

.DESCRIPTION
  Portable. Clone this repo on any Windows box, run this script against any vault.
  Plugin builds are version-pinned and FETCHED from the official GitHub releases at
  install time (gh CLI -> Invoke-WebRequest fallback) so we never vendor third-party
  binaries. For an OFFLINE install, pre-download with scripts\Fetch-Plugins.ps1 and
  pass -OfflineDir. The model profile is MERGED into each plugin's data.json
  (idempotent - safe to re-run / switch backend, merges instead of clobbering).

  Runs on Windows PowerShell 5.1 and PowerShell 7+.

.PARAMETER VaultPath  Vault root (folder with .obsidian). Default: auto-detect from %APPDATA%\obsidian\obsidian.json.
.PARAMETER Backend    local | claude | custom.
.PARAMETER Endpoint   OpenAI-compatible base URL (ends /v1). Used by local/custom.
.PARAMETER ApiKey     Endpoint key. Default 'sk-local' is a placeholder - pass your real key. Never commit a real key.
.PARAMETER Model      Model id served by the endpoint. Default qwopus-9b.
.PARAMETER ClaudeKey  Anthropic key (sk-ant-...). Adds a Claude profile alongside any backend.
.PARAMETER OfflineDir Folder with pre-fetched plugins (from Fetch-Plugins.ps1). Skips network fetch.
.PARAMETER NoEnable   Copy + configure but do not enable.

.EXAMPLE
  .\Install-ObsidianAI.ps1 -Backend local
.EXAMPLE
  .\Install-ObsidianAI.ps1 -VaultPath 'D:\Vaults\Work' -Backend claude -ClaudeKey sk-ant-xxxx
.EXAMPLE
  .\Install-ObsidianAI.ps1 -Backend custom -Endpoint http://10.0.0.5:11434/v1 -ApiKey none -Model qwen2.5
.EXAMPLE
  # offline: pre-fetch at home, copy the folder, install with no network
  .\scripts\Fetch-Plugins.ps1 -Dest .\plugins ; .\Install-ObsidianAI.ps1 -OfflineDir .\plugins -Backend claude -ClaudeKey sk-ant-xxxx
#>
[CmdletBinding()]
param(
  [string]$VaultPath,
  [ValidateSet('local','claude','custom')] [string]$Backend = 'local',
  [string]$Endpoint = 'http://127.0.0.1:8413/v1',
  [string]$ApiKey   = 'sk-local',
  [string]$Model    = 'qwopus-9b',
  [string]$ClaudeKey = '',
  [string]$OfflineDir,
  [switch]$NoEnable,
  [switch]$Interactive
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# version-pinned to builds compatible with Obsidian 1.6.7 (Copilot 3.3.x needs >=1.11.4)
$PluginSpec = @{
  'smart-composer' = @{ repo = 'glowingjade/obsidian-smart-composer'; version = '1.2.9' }
  'copilot'        = @{ repo = 'logancyang/obsidian-copilot';        version = '3.2.8' }
}
$PluginFiles = @('manifest.json','main.js','styles.css')

function Write-JsonNoBom([string]$Path, $Obj) {
  # -InputObject (not pipeline) so PS5.1 never unrolls a top-level single-element array
  $json = ConvertTo-Json -InputObject $Obj -Depth 30
  [System.IO.File]::WriteAllText($Path, $json, (New-Object System.Text.UTF8Encoding($false)))
}
function Read-JsonOrNull([string]$Path) {
  if (Test-Path $Path) {
    $raw = Get-Content -Raw -Encoding UTF8 $Path
    if ($raw.Trim()) { return ($raw | ConvertFrom-Json) }
  }
  return $null
}
function Get-PluginFiles([string]$Id, [string]$Dst) {
  New-Item -ItemType Directory -Force -Path $Dst | Out-Null
  if ($OfflineDir) {
    $src = Join-Path $OfflineDir $Id
    if (-not (Test-Path (Join-Path $src 'main.js'))) { throw "OfflineDir given but $src\main.js not found. Run Fetch-Plugins.ps1 -Dest '$OfflineDir' first." }
    Copy-Item -Force -Recurse (Join-Path $src '*') $Dst
    Write-Host "[+] $Id (offline copy)"
    return
  }
  $repo = $PluginSpec[$Id].repo; $ver = $PluginSpec[$Id].version
  $hasGh = [bool](Get-Command gh -ErrorAction SilentlyContinue)
  foreach ($f in $PluginFiles) {
    $out = Join-Path $Dst $f
    $ok = $false
    if ($hasGh) {
      & gh release download $ver -R $repo -p $f -D $Dst --clobber 2>$null
      $ok = ($LASTEXITCODE -eq 0 -and (Test-Path $out))
    }
    if (-not $ok) {
      $url = "https://github.com/$repo/releases/download/$ver/$f"
      try { Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing -ErrorAction Stop; $ok = $true } catch { $ok = $false }
    }
    if (-not $ok) { throw "Failed to fetch $Id/$f ($repo @ $ver). No gh CLI and direct download blocked? Pre-fetch with Fetch-Plugins.ps1 and use -OfflineDir." }
  }
  Write-Host "[+] $Id ($ver, fetched)"
}

# --- 0. interactive prompts (for the double-click Install.bat path) --------
if ($Interactive) {
  Write-Host "==================================================="
  Write-Host "  Obsidian AI Chat - installer"
  Write-Host "==================================================="
  Write-Host "Pick a model backend:"
  Write-Host "  [1] Claude (Anthropic API) - works anywhere, needs your sk-ant- key   [default]"
  Write-Host "  [2] Custom OpenAI-compatible endpoint (office Ollama / vLLM / LM Studio)"
  $choice = Read-Host "Choice (1/2)"
  if ($choice -eq '2') {
    $Backend  = 'custom'
    $Endpoint = Read-Host "Endpoint base URL (must end with /v1)"
    $kp = Read-Host "API key (leave blank if the endpoint needs none)"
    if ($kp) { $ApiKey = $kp } else { $ApiKey = 'none' }
    $Model    = Read-Host "Model id served by that endpoint"
  } else {
    $Backend = 'claude'
    $sec = Read-Host "Paste your Claude API key (sk-ant-...)" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    try { $ClaudeKey = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    if (-not $ClaudeKey) { throw "No Claude key entered." }
  }
  Write-Host ""
}

# --- 1. resolve vault -------------------------------------------------------
if (-not $VaultPath) {
  $obsJson = Join-Path $env:APPDATA 'obsidian\obsidian.json'
  if (-not (Test-Path $obsJson)) { throw "No -VaultPath given and $obsJson not found. Pass -VaultPath explicitly." }
  $cfg = Get-Content -Raw $obsJson | ConvertFrom-Json
  $vaults = if ($cfg.vaults) { $cfg.vaults.PSObject.Properties.Value } else { @() }
  if (-not $vaults) { throw "obsidian.json has no vault entries. Open a vault in Obsidian once, or pass -VaultPath explicitly." }
  $open = $vaults | Where-Object { $_.open } | Select-Object -First 1
  $VaultPath = if ($open) { $open.path } else { ($vaults | Select-Object -First 1).path }
  Write-Host "[i] Auto-detected vault: $VaultPath"
}
if (-not (Test-Path (Join-Path $VaultPath '.obsidian'))) { throw "Not an Obsidian vault (no .obsidian): $VaultPath" }
$ObsDir  = Join-Path $VaultPath '.obsidian'
$PlugDir = Join-Path $ObsDir 'plugins'
New-Item -ItemType Directory -Force -Path $PlugDir | Out-Null

# --- 2. install plugin files (fetch or offline copy) -----------------------
foreach ($id in $PluginSpec.Keys) { Get-PluginFiles -Id $id -Dst (Join-Path $PlugDir $id) }

# --- 3. enable in community-plugins.json -----------------------------------
if (-not $NoEnable) {
  $cpListPath = Join-Path $ObsDir 'community-plugins.json'
  $list = @(); $existing = Read-JsonOrNull $cpListPath
  if ($existing) { $list = @($existing) }
  foreach ($id in $PluginSpec.Keys) { if ($list -notcontains $id) { $list += $id } }
  Write-JsonNoBom $cpListPath $list
  Write-Host "[+] enabled in community-plugins.json"
}

# --- 4. resolve backend -----------------------------------------------------
$useClaude = ($Backend -eq 'claude')
if ($Backend -eq 'claude' -and -not $ClaudeKey) { throw "-Backend claude requires -ClaudeKey sk-ant-..." }
$claudeModel = 'claude-sonnet-4-5'

function Upsert-ByProp($arr, $prop, $val, $obj) {
  $list = @($arr | Where-Object { $_.$prop -ne $val })
  $list += $obj
  return ,$list
}

# --- 5a. Smart Composer (providers[{type,id,baseUrl,apiKey}], chatModels[{providerType,providerId,id,model}]) ---
$scPath = Join-Path $PlugDir 'smart-composer\data.json'
$sc = Read-JsonOrNull $scPath
if (-not $sc) { $sc = [pscustomobject]@{ providers=@(); chatModels=@() } }
if (-not $sc.PSObject.Properties['providers'])  { $sc | Add-Member providers  @() -Force }
if (-not $sc.PSObject.Properties['chatModels']) { $sc | Add-Member chatModels @() -Force }
if ($useClaude) {
  $sc.providers  = Upsert-ByProp $sc.providers 'id' 'anthropic' ([pscustomobject]@{ type='anthropic'; id='anthropic'; apiKey=$ClaudeKey })
  $sc.chatModels = Upsert-ByProp $sc.chatModels 'id' $claudeModel ([pscustomobject]@{ providerType='anthropic'; providerId='anthropic'; id=$claudeModel; model=$claudeModel })
  $selModel = $claudeModel
} else {
  $sc.providers  = Upsert-ByProp $sc.providers 'id' 'litellm-local' ([pscustomobject]@{ type='openai-compatible'; id='litellm-local'; baseUrl=$Endpoint; apiKey=$ApiKey })
  $sc.chatModels = Upsert-ByProp $sc.chatModels 'id' $Model ([pscustomobject]@{ providerType='openai-compatible'; providerId='litellm-local'; id=$Model; model=$Model })
  $selModel = $Model
}
if (-not $useClaude -and $ClaudeKey) {
  $sc.providers  = Upsert-ByProp $sc.providers 'id' 'anthropic' ([pscustomobject]@{ type='anthropic'; id='anthropic'; apiKey=$ClaudeKey })
  $sc.chatModels = Upsert-ByProp $sc.chatModels 'id' $claudeModel ([pscustomobject]@{ providerType='anthropic'; providerId='anthropic'; id=$claudeModel; model=$claudeModel })
}
$sc | Add-Member chatModelId  $selModel -Force
$sc | Add-Member applyModelId $selModel -Force
Write-JsonNoBom $scPath $sc
Write-Host "[+] configured Smart Composer -> $selModel"

# --- 5b. Copilot (activeModels[{name,provider,baseUrl,apiKey,enabled,isBuiltIn}], defaultModelKey "name|provider") ---
$cpDataPath = Join-Path $PlugDir 'copilot\data.json'
$cp = Read-JsonOrNull $cpDataPath
if (-not $cp) { $cp = [pscustomobject]@{ activeModels=@() } }
if (-not $cp.PSObject.Properties['activeModels']) { $cp | Add-Member activeModels @() -Force }
if ($useClaude) {
  $cpModel = [pscustomobject]@{ name=$claudeModel; provider='anthropic'; enabled=$true; isBuiltIn=$false; apiKey=$ClaudeKey }
  $cpKey   = "$claudeModel|anthropic"
} else {
  $cpModel = [pscustomobject]@{ name=$Model; provider='3rd party (openai-format)'; baseUrl=$Endpoint; apiKey=$ApiKey; enabled=$true; isBuiltIn=$false }
  $cpKey   = "$Model|3rd party (openai-format)"
}
$cp.activeModels = @(@($cp.activeModels | Where-Object { -not ($_.name -eq $cpModel.name -and $_.provider -eq $cpModel.provider) }) + $cpModel)
if (-not $useClaude -and $ClaudeKey) {
  $cl = [pscustomobject]@{ name=$claudeModel; provider='anthropic'; enabled=$true; isBuiltIn=$false; apiKey=$ClaudeKey }
  $cp.activeModels = @(@($cp.activeModels | Where-Object { -not ($_.name -eq $cl.name -and $_.provider -eq $cl.provider) }) + $cl)
}
$cp | Add-Member defaultModelKey $cpKey -Force
Write-JsonNoBom $cpDataPath $cp
Write-Host "[+] configured Copilot -> $cpKey"

# --- 6. done ---------------------------------------------------------------
Write-Host ""
Write-Host "DONE. Vault: $VaultPath"
Write-Host "Backend: $Backend  |  model: $selModel  |  endpoint: $(if($useClaude){'Anthropic API'}else{$Endpoint})"
Write-Host ""
Write-Host "NEXT: In Obsidian press Ctrl+P -> 'Reload app without saving' (or restart Obsidian)."
Write-Host "      Open Smart Composer (left ribbon chat icon) or Copilot Chat and start chatting."
Write-Host "      If the model isn't pre-selected, pick it in the dropdown (provider+endpoint are seeded)."
