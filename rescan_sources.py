#!/usr/bin/env python3
"""Rescan source folders on redsv, add new files to jobs.json/xl_jobs.json as pending.
Called by webstatus /xv/refresh button. Safe: never removes existing entries."""
import json, os, subprocess

BASE = '/home/nothings/xv_convert'
SSH = ['sshpass', '-p', 'fender', 'ssh', '-o', 'StrictHostKeyChecking=no', 'nothings@100.78.228.28']

VIDEO_EXT = ('.mp4', '.mkv', '.avi', '.wmv', '.mov', '.ts')

def scan_remote(setn, remote_dir):
    cmd = subprocess.run(SSH + [f'find "{remote_dir}" -type f \\( '
        + ' -o '.join(f'-name "*{e}"' for e in VIDEO_EXT) + ' \\) -printf "%s|%p\\n"'],
        capture_output=True, text=True, timeout=120)
    out = {}
    for line in cmd.stdout.splitlines():
        if '|' not in line:
            continue
        size_s, path = line.split('|', 1)
        try:
            out[path.lower()] = (int(size_s), path)
        except ValueError:
            continue
    return out

def main():
    added = 0
    for setn, remote_dir, jobs_fn in (
        ('xv', '/mnt/nas4tb/18/xv', 'jobs.json'),
        ('xl', '/mnt/nas4tb/18/xl', 'xl_jobs.json'),
    ):
        jp = os.path.join(BASE, jobs_fn)
        jobs = json.load(open(jp))
        known = {j['src'].lower() for j in jobs}
        remote = scan_remote(setn, remote_dir)
        new_files = []
        for lp, (size, path) in remote.items():
            if lp not in known:
                name = os.path.basename(path)
                if setn == 'xl' and name[:6].lower() in ('s100', 's800', 'defaul'):
                    continue
                jobs.append({'src': path, 'name': name, 'size': size,
                             'status': 'pending', 'percent': 0, 'duration': None,
                             'set': setn})
                new_files.append(f"  + {name} ({size/1e9:.2f}GB)")
                added += 1
        # retry: reset errored jobs back to pending on refresh
        retried = 0
        for j in jobs:
            if j['status'] == 'error':
                j['status'] = 'pending'; j['percent'] = 0; j['error'] = None
                retried += 1
        if retried:
            print(f"{setn}: requeued {retried} errored jobs")
        if new_files or retried:
            json.dump(jobs, open(jp, 'w'), ensure_ascii=False, indent=1)
            print(f"{setn}: added {len(new_files)}")
            for f in new_files:
                print(f)
        else:
            print(f"{setn}: no new files")
    print(f"TOTAL added: {added}")

if __name__ == '__main__':
    main()
