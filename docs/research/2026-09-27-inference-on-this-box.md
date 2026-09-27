# Athena research digest: inference on win-desktop, the problems and what closes them (2026-09-27)

Scope: the two-GPU Windows 11 workstation the lanes run on (RTX 3090 24 GB, RTX 3060 12 GB, 65 GB RAM,
WSL and Docker off since 2026-09-01, native vLLM 0.21 from the SystemPanic fork, llama.cpp behind
llama-swap). The operator's question: why this keeps happening, how others avoid it, and what is closed
by what. Sources: the memory notes of this box since June (43 recorded incidents), the lane logs on
the box, and three web surveys made today on remedies, architectures and the fork's known failures.

## 1. What actually happens here, by class

Forty-three incidents were recorded between June and today. Ranked by count:

| class | incidents | the shape of it |
|---|---|---|
| launcher and scheduler | 12 | duplicate starts, a supervisor killing live lanes on a WMI lie or killing `dwm.exe`, config reloads restarting everything, port clashes (8001 taken, rpc 29550 shared), stall limits too short on the HDD |
| VRAM zombies and squatters | 10 | an EngineCore child outliving its parent, a RAG service or an eval script parked on the 3090, a foreign llama-server on :8091 (23.09 and again today), NVIDIA Overlay eating the 3060 |
| configuration arithmetic | 6 | concurrency equal to slots (no KV headroom), context larger than max-model-len, the driver's reserve ignored, an fp8 script swapped in by another session |
| runtime bugs of the fork | 4 | fp8 KV forcing a FlashInfer JIT that dies on the cp1251 path, the V2 runner's int32 seed, a workspace-lock growth, a start hanging in JIT |
| host RAM and commit | 2 recorded, one more today | the commit ceiling at 141 GB in September; today `memory allocation of 1048576 bytes failed` inside vLLM at 20:02 while crosshair, cosmic-ray, pytest and two of the operator's GPU jobs ran beside two lanes |
| quant format, disk, network | 5 | wrong quant format for GDN, MXFP4 slow on ik_llama, HDD queue depth freezing the host, a cost-map fetch blocked by the firewall |

Two facts from the logs today: the vanilla 9B lane has restarted 54 times since 1 September, eleven
times on each of 23.09 and 25.09; the OmniCoder lane died today from host memory, then could not
restart because its `--gpu-memory-utilization 0.70` demands 16.8 GB while a zombie of its own previous
life held 8 GB and two foreign jobs held the rest. The homegrown PowerShell supervisor of August and
September caused as many of the 43 incidents as it fixed (it killed `dwm.exe`, killed live lanes when
WMI answered empty, started duplicates); that is the strongest single argument for a boring OSS
supervisor over another script.

## 2. Why Windows makes each class worse

- No OOM killer: when commit runs out the next allocation fails in whichever process asks, today it
  was vLLM. Commit here is 145 GB (65 RAM + 80 pagefile), peak pagefile use today 9.7 GB, so the
  failure was a burst, not a ceiling.
- Children do not die with their parent: vLLM's own tree kill uses `SIGKILL`, which does not exist on
  Windows, so the EngineCore process survives every crash of the API server (fork issue #79, patch
  proposed August 2026).
- The fraction is of total VRAM, checked before anything loads: `--gpu-memory-utilization` is a
  demand, not a request; a neighbour on the card makes the restart impossible until someone frees it.
- WDDM, not TCC: no `EXCLUSIVE_PROCESS` compute mode on GeForce, NVML cannot report per-process VRAM,
  and the driver's "sysmem fallback" spills VRAM into RAM silently instead of failing.
- llama-swap is a router: it relaunches a dead upstream only on the next request, its health-check
  timeout (1200 s in our config) blocks the queue for twenty minutes on a failed start, and it knows
  nothing of a stranger on the card.
- Task Scheduler runs things under other accounts, invisible from a normal shell: the :8091 server.

## 3. What closes what

| failure | closed by | tool / setting | licence | native | residual |
|---|---|---|---|---|---|
| host-RAM death of a lane | a commit ceiling per process tree, so the runaway hits its own cap | `procgov --maxjobmem <N>G -r --terminate-job-on-exit` around each lane and each heavy gate | MIT | yes | a burst below the caps still competes; pair with the admission floor below |
| EngineCore zombie | no child at all, or a job that dies with its parent | `VLLM_ENABLE_V1_MULTIPROCESSING=0` (already set on the omni lane) and the job object's kill-on-close | Apache-2.0 / OS | yes | a hung CUDA context can outlive TerminateProcess until the driver reclaims it |
| restart refused on a fixed fraction | absolute KV bytes plus a fraction the card can meet | `--kv-cache-memory-bytes <value vLLM logs at a clean start>` with `--gpu-memory-utilization` derived from measured free VRAM at launch | Apache-2.0 | yes | the guard is still evaluated on the fraction (vLLM #20305); the launcher must re-measure each boot |
| lazy relaunch, twenty-minute block | a real supervisor owns restarts, llama-swap only routes | WinSW `onfailure restart` with backoff and tree kill (or NSSM, or llamactl's `auto_restart`), `healthCheckTimeout` 120 to 180 s | MIT / public domain | yes | a wedged-but-alive upstream needs an outside prober (`/metrics`, not `/health`) |
| silent spill to system RAM | fail loudly | NVIDIA Control Panel: CUDA Sysmem Fallback Policy = Prefer No Sysmem Fallback, per exe | driver | yes | none |
| foreign process on the card | an inventory and a poller | a pynvml poller, elevated, comparing compute PIDs per GPU to an allow-list of executables; alert into bd | Apache-2.0 (nvitop as the base) | yes | can see presence, not size; cannot prevent, only report |
| commit ceiling | a pagefile you chose | fixed 64 to 128 GB on NVMe; memory compression left on | OS | yes | slower under pressure instead of dead |
| `/health` lying under load | admit on metrics | `vllm:num_requests_waiting`, `kv_cache_usage_perc`, `corrupted_requests_total`, `/load` with `--enable-server-load-tracking` | Apache-2.0 | yes | the frame's admission (C-4.2) already reads these; the crash today was the reader's, fixed |
| the fork's own bugs | flags to avoid | no fp8 KV (FlashInfer JIT on a cp1251 path), no speculative config on GDN (open PRs #40738, #56531), no prefix caching on GDN in align mode (NaN checkpoints, #55766), `VLLM_USE_V2_MODEL_RUNNER=0`, `--swap-space 0`, `--mm-processor-cache-gb 0` | — | — | the omni lane still runs `--kv-cache-dtype fp8` and `--enable-prefix-caching`: both on the avoid list |

## 4. How others structure it

Three architectures survive contact with this box. (1) Native Windows, llama-swap as the data plane,
WinSW as the supervisor of llama-swap and of each vLLM, procgov around each process tree; VRAM by
config discipline only. (2) llamactl instead of llama-swap: a real restart policy (`max_restarts`,
`restart_delay`), idle timeout, LRU, per-group limits; younger, Windows stop fixed in 2026, to be
verified here. (3) Either of those plus a Linux control plane over the LAN: Prometheus on ai-server
scraping windows_exporter's GPU collector, nvidia_gpu_exporter as a Windows service, llama-swap's
`/metrics`, and uptime-kuma push monitors so a stalled lane is seen from outside. GPUStack is out
(Linux-only workers since v2), Ollama and LM Studio are login apps with opaque VRAM juggling, Hyper-V
GPU partitioning for a Linux guest on GeForce is the WSL path with more moving parts and no VRAM
bound in the guest either.

What no native setup gives: a VRAM quota per process, a scheduler that places by measured free VRAM,
an OOM killer for the GPU. Every tool above places by static config. The frame's admission is the
closest thing to a scheduler this box will have, which is why it belongs in the frame as clauses.

## 5. The plan for this box, in order of leverage

1. Lane launchers under WinSW plus procgov: restart with backoff, tree kill, a commit ceiling per lane
   (32 GB for a vLLM lane, 8 GB for llama.cpp), `healthCheckTimeout` 180 in llama-swap. Our two lanes
   first (omni, nanbeige); the operator's 9B lane only on his word.
2. Absolute KV on the omni lane: read the bytes vLLM logs on a clean start, pin them, derive the
   fraction from free VRAM at launch; drop fp8 KV and prefix caching there (both on the avoid list;
   turboquant or `auto` instead).
3. Resource floors in the frame's admission (C-4.2): free RAM and free VRAM before a dispatch and
   before any heavy gate; heavy gates serialised and inside procgov.
4. The inventory poller: allow-list per GPU, elevated, windowless, one bead per stranger.
5. Sysmem fallback off for python.exe and llama-server.exe; the pagefile stays at 80 GB, it was not
   the ceiling today.
6. A venv for the frame so a pip install never breaks the interpreter the lanes and the checks share
   (today's aiohttp breakage).
7. The daemon wakes a `ttl: 0` lane through llama-swap when it sees no lane state, then parks.

Items 3, 4 and 7 are clauses of the perimeter layer's next group (C-5, the substrate) and go through
the lanes; 1, 2, 5 and 6 are host changes, done by hand with the diff shown; the 9B lane and the
operator's own GPU jobs are his.

Sources: memory notes under `~/.claude/projects/.../memory/` (reference_windesktop_vllm_lanes_map,
reference_llamaswap_kv_overflow_stability, reference_native_win_vllm_fp8_flashinfer_cp1251,
reference_vllm_gdn_speed_config and the rest of the lane series), `D:/tmp/lanes/lane-omni.log`,
`D:/tmp/lanes/lane9b.log`, llama-swap `/logs`; procgov (lowleveldesign/process-governor), WinSW,
NSSM, shawl, llamactl, llama-swap wiki, vLLM docs on multiprocessing, cache config and conserving
memory, vLLM issues #20305, #39863, #55766, #39273, PRs #40738, #56531, #57018, SystemPanic issues
#79 and #85, NVIDIA KB on sysmem fallback, NVML on WDDM forum threads, Microsoft docs on job objects
and pagefile sizing, windows_exporter gpu collector, nvidia_gpu_exporter, GPUStack migration notes,
Easy-GPU-PV archive notice.
