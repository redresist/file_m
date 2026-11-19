#!/usr/bin/env python3
"""xv+xl convert status page: merged list, pending interleaved by size (alternating sets),
finished/skipped after. Serves 127.0.0.1:8899 at /xv."""
import json, os, subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE_DIR = '/home/nothings/xv_convert'
PAUSE = os.path.join(BASE_DIR, 'PAUSE')

HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>xv + xl convert</title>
<meta http-equiv="refresh" content="5">
<style>
body{font-family:system-ui;background:#111;color:#ddd;margin:20px}
h1{font-size:20px} h2{font-size:14px;color:#999;margin:4px 0 12px}
.bar{background:#333;border-radius:4px;height:14px;width:120px;display:inline-block;vertical-align:middle}
.bar div{background:#4caf50;height:14px;border-radius:4px}
table{border-collapse:collapse;width:100%;font-size:13px;margin-top:12px}
td,th{border-bottom:1px solid #333;padding:5px 8px;text-align:left}
th{color:#999}
.done{color:#4caf50}.running{color:#ff9800;font-weight:bold}.detecting{color:#2196f3}
.pending{color:#777}.error{color:#f44336}.skip{color:#555}
.set-xv{color:#7fc7ff}.set-xl{color:#ffb0d8}
.summary{font-size:15px;margin:8px 0}
button{background:#333;color:#ddd;border:1px solid #555;padding:6px 16px;border-radius:4px;cursor:pointer;font-size:14px}
button:hover{background:#444}
.pause-on{color:#ff9800;font-weight:bold}
</style></head><body>
<h1>xv + xl mosaic convert</h1>
<h2>nas 18/xv &rarr; 18/xv-convert &nbsp;&nbsp;+&nbsp;&nbsp; nas 18/xl &rarr; 18/xl-convert</h2>
<div class="summary">{SUMMARY}</div>
<a href="/xv/toggle"><button>{PAUSE_BTN}</button></a>
<a href="/xv/refresh"><button>&#8635; REFRESH (rescan new files)</button></a>
<table>
<tr><th>#</th><th>Set</th><th>File</th><th>Size</th><th>Status</th><th>Progress</th><th>ETA</th></tr>
{ROWS}
</table></body></html>"""

def fmt_size(n):
    if n >= 1e9: return f"{n/1e9:.2f}GB"
    if n >= 1e6: return f"{n/1e6:.0f}MB"
    return f"{n/1e3:.0f}KB"

def fmt_eta(j):
    if j['status'] != 'running' or not j.get('duration') or not j.get('percent'):
        return ''
    remain = j['duration'] * (100 - j['percent']) / 100
    if remain < 90: return f"{remain:.0f}s"
    if remain < 5400: return f"{remain/60:.0f}m"
    return f"{remain/3600:.1f}h"

def load(setn):
    fn = 'jobs.json' if setn == 'xv' else 'xl_jobs.json'
    try:
        jobs = json.load(open(f'{BASE_DIR}/{fn}'))
        for j in jobs: j['_set'] = setn
        return jobs
    except Exception:
        return []

def render():
    xv, xl = load('xv'), load('xl')
    paused = os.path.exists(PAUSE)
    all_j = xv + xl
    done = [j for j in all_j if j['status'] == 'done']
    err = [j for j in all_j if j['status'] == 'error']
    skip = [j for j in all_j if j['status'] == 'skip']
    run = next((j for j in all_j if j['status'] in ('running', 'detecting')), None)
    total_gb = sum(j['size'] for j in all_j) / 1e9
    pend_xv = sum(1 for j in xv if j['status'] == 'pending')
    pend_xl = sum(1 for j in xl if j['status'] == 'pending')
    s = (f"Total {len(all_j)} files ({total_gb:.0f}GB) &mdash; done {len(done)}, "
         f"pending xv {pend_xv} + xl {pend_xl}, skipped {len(skip)}, errors {len(err)}")
    if run:
        s += f" &mdash; NOW[{run['_set']}]: {run['name'][:40]} {run['percent']}%"
    if paused:
        s += ' &mdash; <span class="pause-on">PAUSED</span>'

    # DONE group (top, unnumbered): by finish time
    done_sorted = sorted(done, key=lambda x: x.get('finished', 0))
    # QUEUE (numbered, processing order): running/detecting first, then pending interleaved xv/xl size-asc
    run_row = [j for j in all_j if j['status'] in ('running', 'detecting')]
    xvp = sorted([j for j in xv if j['status'] == 'pending'], key=lambda x: x['size'])
    xlp = sorted([j for j in xl if j['status'] == 'pending'], key=lambda x: x['size'])
    queue = run_row
    i = j = 0
    while i < len(xvp) or j < len(xlp):
        if i < len(xvp): queue.append(xvp[i]); i += 1
        if j < len(xlp): queue.append(xlp[j]); j += 1
    # SKIPPED group (bottom, unnumbered)
    skip_sorted = sorted(skip, key=lambda x: (x['_set'], x['size']))
    err_sorted = sorted(err, key=lambda x: (x['_set'], x['size']))

    rows = []
    def add_row(j, num=None):
        st = j['status']; pct = j.get('percent', 0)
        if st in ('running', 'done'):
            bar = f'<div class="bar"><div style="width:{pct}%"></div></div> {pct}%'
        elif st == 'skip':
            bar = j.get('skip_reason', '')[:34]
        elif st == 'error':
            bar = j.get('error', '')[:34]
        else:
            bar = ''
        numtxt = str(num) if num is not None else '&mdash;'
        rows.append(f'<tr><td>{numtxt}</td><td class="set-{j["_set"]}">{j["_set"]}</td>'
                    f'<td title="{j["src"]}">{j["name"][:60]}</td>'
                    f'<td>{fmt_size(j["size"])}</td><td class="{st}">{st}</td>'
                    f'<td>{bar}</td><td>{fmt_eta(j)}</td></tr>')

    rows.append('<tr><td colspan="7" style="color:#4caf50;font-weight:bold;padding-top:14px">DONE (unnumbered)</td></tr>')
    for j in done_sorted: add_row(j)
    rows.append('<tr><td colspan="7" style="color:#ff9800;font-weight:bold;padding-top:14px">QUEUE (processing order, top runs next)</td></tr>')
    qn = 1
    for j in queue:
        add_row(j, qn); qn += 1
    rows.append('<tr><td colspan="7" style="color:#555;font-weight:bold;padding-top:14px">SKIPPED (ads / no censor / duplicates / preview variants &mdash; no run needed)</td></tr>')
    for j in skip_sorted: add_row(j)
    if err_sorted:
        rows.append('<tr><td colspan="7" style="color:#f44336;font-weight:bold;padding-top:14px">ERRORS (will retry)</td></tr>')
        for j in err_sorted: add_row(j)

    btn = '&#9654; RESUME' if paused else '&#9208; PAUSE (free GPU)'
    return (HTML.replace('{SUMMARY}', s).replace('{PAUSE_BTN}', btn)
                .replace('{ROWS}', '\n'.join(rows)))

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        p = self.path.split('?')[0]
        if p.startswith('/xv/refresh'):
            subprocess.Popen(['python3', '/home/nothings/xv_convert/rescan_sources.py'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.send_response(302)
            self.send_header('Location', '/xv')
            self.end_headers()
            return
        if p in ('/xv/toggle', '/toggle') or p.startswith('/xv/toggle'):
            if os.path.exists(PAUSE): os.remove(PAUSE)
            else: open(PAUSE, 'w').close()
            self.send_response(302)
            self.send_header('Location', '/xv')
            self.end_headers()
            return
        if p in ('/xv', '/xv/', '/'):
            body = render().encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()
    def log_message(self, *a): pass

if __name__ == '__main__':
    HTTPServer(('0.0.0.0', 8899), H).serve_forever()
