# obsidian-ai-pack

Portable one-click deploy of in-vault **AI chat for agents** into *any* Obsidian on
*any* Windows box. Bundles two chat plugins + a PowerShell installer that wires them
to a model backend (local swarm / Claude / any OpenAI-compatible endpoint).

> Goal: clone this repo at work (or on a fresh machine), run one command, and have a
> working agent chat **inside Obsidian** pointed at whatever model you have there.

## What's in the box

```
obsidian-ai-pack/
├─ Install-ObsidianAI.ps1          # the one-click installer (fetch + enable + configure)
├─ config-templates/               # data.json schema reference (installer builds these live)
├─ scripts/
│  ├─ Fetch-Plugins.ps1            # pre-download pinned plugin builds for OFFLINE install
│  └─ Setup-WslLitellmProxy.ps1    # HOME-only: expose a WSL litellm to Windows
└─ README.md
```

The two plugins (**Smart Composer 1.2.9** — MCP-aware chat + inline edits; **Copilot 3.2.8**
— second-brain chat/QA) are **version-pinned to builds compatible with Obsidian 1.6.7+**
(Copilot 3.3.x needs ≥1.11.4) and **fetched from their official GitHub releases at install
time** (gh CLI → `Invoke-WebRequest` fallback). We don't vendor the binaries: they carry
the vendor's own embedded OAuth client ids (which trip GitHub push protection) and would
bloat the repo. For an **offline** install, pre-fetch with `Fetch-Plugins.ps1` and pass
`-OfflineDir` (see example D).

## Quick start

```powershell
# clone, then from the pack dir:
cd obsidian-ai-pack

# A) Claude (works anywhere, instant) -- BEST for reconcile/synthesis
.\Install-ObsidianAI.ps1 -Backend claude -ClaudeKey sk-ant-XXXX

# B) Any OpenAI-compatible box (office Ollama / vLLM / LM Studio)
.\Install-ObsidianAI.ps1 -Backend custom -Endpoint http://10.0.0.5:11434/v1 -ApiKey none -Model qwen2.5

# C) Home local swarm (WSL litellm) -- usually just works:
#    WSL2 localhostForwarding maps Windows 127.0.0.1:8413 -> the WSL litellm (loopback,
#    firewall-exempt). So the default endpoint is correct, no bridge needed.
.\Install-ObsidianAI.ps1 -Backend local
#    Fallback ONLY if 127.0.0.1:8413 is not reachable (localhostForwarding off):
#    $u = .\scripts\Setup-WslLitellmProxy.ps1 | Select-Object -Last 1
#    .\Install-ObsidianAI.ps1 -Backend custom -Endpoint $u -ApiKey <litellm-master-key> -Model qwopus-9b

# D) OFFLINE (no network on the target machine): pre-fetch at home, copy the folder, install
.\scripts\Fetch-Plugins.ps1 -Dest .\plugins
.\Install-ObsidianAI.ps1 -OfflineDir .\plugins -Backend claude -ClaudeKey sk-ant-XXXX
```

> Requires `gh` CLI or internet access at install time (to fetch the plugin builds),
> unless you use the offline `-OfflineDir` flow above.

Then in Obsidian: **Ctrl+P → "Reload app without saving"** (or restart). Open the
Smart Composer chat (left ribbon) or Copilot Chat and go. If the model isn't pre-
selected, pick it in the dropdown — the provider + endpoint + key are already seeded.

## Locked-down office machine (nothing installed)

Designed for a vanilla, restricted Windows box: **no git, no gh, no dev tools, GitHub
maybe blocked, no admin rights.** Everything writes only inside your own vault — no
system changes, no firewall, no admin.

**At home (once):** build a self-contained bundle.
```powershell
cd obsidian-ai-pack
.\scripts\Build-OfflineBundle.ps1      # fetches plugins + zips -> dist\obsidian-ai-pack-offline.zip
```
Carry `obsidian-ai-pack-offline.zip` to the office (USB / email / cloud).

**At the office:**
1. Right-click the ZIP → **Properties → Unblock** (clears "mark of the web"), then extract.
2. **Double-click `Install.bat`** → it runs the installer with a per-process execution-policy
   bypass (works on the default Restricted/RemoteSigned policies) and asks for your Claude
   key (or a custom endpoint). No PowerShell window to open, no command to type.
3. In Obsidian: Ctrl+P → "Reload app without saving". Done.

**If even `Install.bat` is blocked** (machine-level GPO `AllSigned` — the one wall a script
can't pass): open **`MANUAL-INSTALL.txt`** — a 2-minute, zero-script, no-admin path (drag the
two plugin folders into `.obsidian\plugins\`, enable them in Obsidian's Community-plugins UI,
paste your key in the plugin settings). The plugins are already in the bundle, so no internet
is needed for the install — only access to your chosen model (Claude or an office endpoint).

### Installer parameters

| Param | Meaning | Default |
|------|---------|---------|
| `-VaultPath` | Vault root (folder with `.obsidian`) | auto-detect open vault |
| `-Backend` | `local` \| `claude` \| `custom` | `local` |
| `-Endpoint` | OpenAI-compatible base URL (ends `/v1`) | `http://127.0.0.1:8413/v1` |
| `-ApiKey` | key for the endpoint (pass your real one; for home litellm = its master_key) | `sk-local` (placeholder) |
| `-Model` | model id served | `qwopus-9b` |
| `-ClaudeKey` | `sk-ant-...`; adds a Claude profile alongside any backend | — |
| `-NoEnable` | copy + configure but don't enable | off |

The installer is **idempotent**: it merges its provider/model into an existing
`data.json` instead of overwriting, so re-running (e.g. to switch backend) is safe.

## Switching backends later

Re-run the installer with a different `-Backend`. Both a local and a Claude profile
can coexist (pass `-ClaudeKey` together with a local/custom backend); switch between
them in each plugin's model dropdown. Core chat on local for privacy, deep synthesis
on Claude.

## Layered picture (where this sits)

- **L0** Obsidian Local REST API plugin — REST surface into the vault.
- **L1** `obsidian-mcp-server` (cyanheads) — MCP tools for the Hermes/NEXUS swarm to read/write the vault.
- **L2** self-maintaining second-brain agents (rewrite / reconcile / scheduled) — the wiki keeps itself current.
- **L3 (this pack)** in-vault chat — talk to an agent *right there* in Obsidian. Smart Composer is MCP-aware, so it can also drive the L1 tools.

## Notes / gotchas

- **Reaching a WSL litellm from Windows**: WSL2 `localhostForwarding` (on by default)
  maps a service bound to `127.0.0.1` inside WSL to `127.0.0.1` on Windows — so
  `-Backend local` (endpoint `127.0.0.1:8413`) just works, no bridge, no firewall rule.
  Only if that's disabled use `Setup-WslLitellmProxy.ps1` (and note: a non-loopback
  WSL-IP endpoint also needs an outbound firewall allow if you run default-deny outbound).
  (All irrelevant at work — use Claude/office endpoint.)
- The local swarm endpoint only exists at home; at work use `-Backend claude` or `custom`.
- Smart Composer needs Obsidian ≥0.15.0; Copilot 3.2.8 needs ≥0.15.0 (both fine on 1.6.7).
- Secrets (API keys) live only in the target vault's `.obsidian/plugins/*/data.json`.
  Don't commit a configured vault's data.json to a public repo.
