# file_m

Single-file Python HTTP file manager + media streaming server for LAN/tailnet media drives.
No dependencies beyond Python 3 stdlib. Two variants in this repo:

| File | Runs on | Port | Serves |
|---|---|---|---|
| `gmedia_server.py` | redrevival (WSL) | 8850 | `G:\back2tb\xv` (source backup) + `G:\xv_results` (converted outputs) |
| `gmedia_redsv.py` | redsv (Linux) | 8810 | `/mnt/nas4tb/18` — `xv/`, `xl/`, `xv-convert/`, `xl-convert/` (4TB disk from retired NAS) |

## What it does

- Directory browser (HTML, mobile-friendly, works in any browser)
- Direct file links with **HTTP Range streaming** — seek works, plays in VLC / mobile players via
  "open network stream" → `http://<host>:<port>/<set>/<file>.mp4`
- `[VLC direct]` link next to every media file
- Read-only by design
- Path traversal protection (all paths confined to their root)

## Run

```bash
python3 gmedia_server.py        # or gmedia_redsv.py on redsv
```

Runs in foreground; on redsv it runs under PM2 as `gmedia-8810`:

```bash
pm2 start gmedia_redsv.py --name gmedia-8810
pm2 save
```

## Access

- Browser: `http://<host-ip>:<port>/`
- VLC (mobile): Network stream → `http://<host-ip>:<port>/xv_results/<file>.mp4`
- Over tailscale: `https://redsv.tailb6b666.ts.net/xv` (tailscale serve `--set-path=/xv http://127.0.0.1:8810`)

## Changing served paths

Edit the `ROOTS` dict at the top of the file (name → filesystem path), restart.

## Context

Built 2026-11-19 when the QNAP TS-251+ (rednas) chassis failed (sys fan dead → SATA backplane
unstable → both bays fail both disks). NAS retired; 4TB disk moved into redsv. These servers
replaced the NAS's FileBrowser (:8810) and rclone (:8800) file-access roles.

## Related

- Convert pipeline (lada mosaic removal) lives on redrevival: `~/xv_convert/driver_alt.py`
- Fleet notes: `redresist/ai-stack` repo, redsv/redrevival status dashboards
