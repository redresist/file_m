#!/usr/bin/env python3
"""File manager + media server for G: drives (NAS-down period).
Serves G:/back2tb/xv (source backup) and G:/xv_results (converted) as browsable HTML + direct
file links playable by VLC (mobile on tailscale/LAN). Binds 0.0.0.0:8850 (LAN + tailnet reachable).
Read-only. No auth (tailnet/LAN is the gate), like the old rclone :8800 NAS server."""
import os, html, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

ROOTS = {
    'xv': '/mnt/nas4tb/18/xv',
    'xl': '/mnt/nas4tb/18/xl',
    'xv_results': '/mnt/nas4tb/18/xv-convert',
    'xl_results': '/mnt/nas4tb/18/xl-convert',
}
PORT = 8810

def fmt_size(n):
    for u in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024: return f"{n:.0f}{u}" if u in ('B','KB') else f"{n:.1f}{u}"
        n /= 1024
    return f"{n:.1f}PB"

def is_media(name):
    return name.lower().endswith(('.mp4','.mkv','.avi','.wmv','.mov','.ts','.webm','.m4v'))

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urllib.parse.unquote(self.path)
        parts = path.strip('/').split('/', 1)
        setn = parts[0] if parts and parts[0] in ROOTS else None
        rel = parts[1] if len(parts) > 1 else ''
        if not setn:
            # index: list roots
            rows = ''.join(f'<tr><td><a href="/{k}/">&#128193; {k}</a></td>'
                           f'<td>{html.escape(v)}</td></tr>' for k, v in ROOTS.items())
            body = PAGE_TMPL.replace('{TITLE}', 'redsv media').replace('{ROWS}', rows)
            self._send(200, body)
            return
        base = ROOTS[setn]
        full = os.path.normpath(os.path.join(base, rel))
        if not full.startswith(base):
            self._send(403, 'forbidden'); return
        if os.path.isdir(full):
            self._dir(setn, rel, full)
        elif os.path.isfile(full):
            self._file(full)
        else:
            self._send(404, 'not found')

    def _dir(self, setn, rel, full):
        rows = []
        if rel:
            up = f'/{setn}/' + '/'.join(rel.split('/')[:-1])
            rows.append(f'<tr><td><a href="{up}">&#11014; ..</a></td><td></td></tr>')
        try:
            entries = sorted(os.listdir(full), key=str.lower)
        except Exception as e:
            rows.append(f'<tr><td colspan=2>error: {html.escape(str(e))}</td></tr>')
            entries = []
        for name in entries:
            p = os.path.join(full, name)
            link = f'/{setn}/' + (rel + '/' if rel else '') + name
            link = urllib.parse.quote(link)
            if os.path.isdir(p):
                rows.append(f'<tr><td><a href="{link}/">&#128193; {html.escape(name)}</a></td><td></td></tr>')
            else:
                size = fmt_size(os.path.getsize(p))
                if is_media(name):
                    q = urllib.parse.quote(link)
                    rows.append(f'<tr><td>&#127916; <a href="{link}">{html.escape(name)}</a> '
                                f'<a href="{q}" style="color:#7fc7ff">[VLC direct]</a></td>'
                                f'<td>{size}</td></tr>')
                else:
                    rows.append(f'<tr><td><a href="{link}">{html.escape(name)}</a></td><td>{size}</td></tr>')
        title = f'{setn}/{rel}' if rel else setn
        body = PAGE_TMPL.replace('{TITLE}', html.escape(title)).replace('{ROWS}', '\n'.join(rows))
        self._send(200, body)

    def _file(self, full):
        size = os.path.getsize(full)
        ctype = 'video/mp4' if full.endswith('.mp4') else 'video/x-matroska' if full.endswith('.mkv') else \
                'video/avi' if full.endswith('.avi') else 'application/octet-stream'
        range_header = self.headers.get('Range')
        if range_header:
            m = range_header.replace('bytes=', '').split('-')
            start = int(m[0]) if m[0] else 0
            end = int(m[1]) if len(m) > 1 and m[1] else size - 1
            end = min(end, size - 1)
            length = end - start + 1
            self.send_response(206)
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Length', str(length))
            self.send_header('Content-Type', ctype)
            self.end_headers()
            with open(full, 'rb') as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(1024*512, remaining))
                    if not chunk: break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        else:
            self.send_response(200)
            self.send_header('Content-Length', str(size))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Type', ctype)
            self.end_headers()
            with open(full, 'rb') as f:
                while True:
                    chunk = f.read(1024*512)
                    if not chunk: break
                    self.wfile.write(chunk)

    def _send(self, code, body):
        body = body.encode()
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a): pass

PAGE_TMPL = '''<!DOCTYPE html><html><head><meta charset="utf-8"><title>{TITLE}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:system-ui;background:#111;color:#ddd;margin:14px;font-size:14px}
a{color:#ddd;text-decoration:none}a:hover{color:#fff}
table{border-collapse:collapse;width:100%}td{padding:5px 6px;border-bottom:1px solid #333}
td:nth-child(2){color:#888;text-align:right;white-space:nowrap}
h1{font-size:18px}</style></head><body>
<h1>{TITLE}</h1><table>{ROWS}</table></body></html>'''

if __name__ == '__main__':
    HTTPServer(('0.0.0.0', PORT), H).serve_forever()
