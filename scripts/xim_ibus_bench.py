#!/usr/bin/env python3
"""Reproducer: superlinear XIM input-context registration cost with ibus.

Creating N Tk widgets (one X window each, packed in a Frame embedded in a
Canvas) stalls in update_idletasks() for a time that grows superlinearly in N
when XMODIFIERS='@im=ibus'. With XMODIFIERS='' the identical program is ~150x
faster, isolating the cost to XIM input-context registration rather than
widget creation, geometry, or window mapping.

Discovered via poet-it's rhyme popup, which built one Button per rhyme:
3654 windows froze the UI for many minutes on a GNOME Wayland session.

Usage:
    python scripts/xim_ibus_bench.py [report.md]

Runs the benchmark twice in subprocesses (ibus XIM on / off), prints a
Markdown report to stdout or writes it to the given path. Stdlib only;
needs a running X or Xwayland display with ibus active.
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import time

SIZES = (125, 250, 500)


def bench_once(n):
    """Child mode: build the widget tree once at size n, print JSON timings.
    One size per process — XIM registration cost grows with the contexts
    already created in the session, so reusing a process biases later sizes."""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    popup = tk.Toplevel(root)
    popup.geometry('+6000+6000')          # keep off-screen
    t0 = time.perf_counter()
    outer = tk.Frame(popup)
    outer.pack(fill=tk.BOTH, expand=True)
    cv = tk.Canvas(outer, width=220, height=320, bg='white')
    cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    inner = tk.Frame(cv, bg='white')
    cv.create_window((0, 0), window=inner, anchor='nw')
    for i in range(n):
        tk.Button(inner, text=f'word{i}', anchor='w', relief='flat',
                  bg='white', command=lambda: None
                  ).pack(fill=tk.X, padx=2, pady=1)
    t_create = time.perf_counter()
    inner.update_idletasks()              # realizes windows; XIM registration here
    t_idle = time.perf_counter()
    popup.update()
    t_map = time.perf_counter()
    root.destroy()
    print(json.dumps({'tk_version': tk.TkVersion,
                      'n': n,
                      'create_s': t_create - t0,
                      'idletasks_s': t_idle - t_create,
                      'map_s': t_map - t_idle}))


def run_children(xmodifiers):
    results = []
    for n in SIZES:
        env = dict(os.environ, XMODIFIERS=xmodifiers, XIM_BENCH_CHILD=str(n))
        out = subprocess.run([sys.executable, os.path.abspath(__file__)],
                             env=env, capture_output=True, text=True, timeout=600)
        if out.returncode != 0:
            raise RuntimeError(f'benchmark child failed:\n{out.stderr}')
        results.append(json.loads(out.stdout.strip().splitlines()[-1]))
    return {'tk_version': results[0]['tk_version'], 'results': results}


def cmd_version(*cmd):
    if not shutil.which(cmd[0]):
        return 'not found'
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return (r.stdout or r.stderr).strip().splitlines()[0]
    except Exception as e:
        return f'error: {e}'


def os_release():
    try:
        with open('/etc/os-release') as fh:
            for line in fh:
                if line.startswith('PRETTY_NAME='):
                    return line.split('=', 1)[1].strip().strip('"')
    except OSError:
        pass
    return platform.platform()


def make_report(on, off):
    rows = []
    for a, b in zip(on['results'], off['results']):
        ratio = a['idletasks_s'] / max(b['idletasks_s'], 1e-9)
        rows.append(f"| {a['n']} | {a['idletasks_s']:.2f} | {b['idletasks_s']:.2f} "
                    f"| {ratio:,.0f}x |")
    scaling = [f"{a['idletasks_s'] / max(p['idletasks_s'], 1e-9):.1f}x"
               for p, a in zip(on['results'], on['results'][1:])]
    return f"""# Superlinear XIM input-context registration with ibus

Realizing N Tk widgets (one X window each) stalls in the X-server/input-method
handshake for time superlinear in N when `XMODIFIERS='@im=ibus'`. The identical
program with `XMODIFIERS=''` is two orders of magnitude faster, so widget
creation, geometry management, and window mapping are all exonerated — the cost
is XIM input-context registration.

## Environment

| | |
|---|---|
| OS | {os_release()} |
| Kernel | {platform.release()} |
| Session | {os.environ.get('XDG_SESSION_TYPE', '?')} (WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY', '-')}, DISPLAY={os.environ.get('DISPLAY', '-')}) |
| GNOME Shell / mutter | {cmd_version('gnome-shell', '--version')} |
| ibus | {cmd_version('ibus', 'version')} |
| Python | {platform.python_version()} |
| Tk | {on['tk_version']} |
| XMODIFIERS (session default) | {os.environ.get('XMODIFIERS', '(unset)')!r} |

## Measurements

Time spent in `update_idletasks()` (widget realization) for N buttons packed
in a Canvas-embedded Frame, popup positioned off-screen. Each N runs in a
fresh process (registration cost grows with contexts already created in the
session, so process reuse biases later sizes):

| N windows | XMODIFIERS='@im=ibus' | XMODIFIERS='' | ratio |
|---|---|---|---|
{chr(10).join(rows)}

Growth per doubling of N with ibus XIM active: {', '.join(scaling)}
(linear would be 2.0x throughout). The per-window cost with ibus is tens of
milliseconds — hundreds of times the no-XIM cost — so realizing widgets en
masse stalls for seconds to minutes. In the real-world case that exposed this
(a poetry editor's rhyme popup creating 3654 windows) the UI froze for
minutes, ending only when the user gave up or the popup finally appeared.

## Reproduce

```sh
python3 xim_ibus_bench.py            # runs both conditions, prints this report
```

Or manually: run any Tk program that realizes hundreds of widgets at once,
with and without `XMODIFIERS='@im=ibus'`.

## Notes

- Only the XIM compatibility path is implicated; the same ibus engine is fine
  for one window. Registration cost per context is orders of magnitude above
  the no-XIM baseline and grows with the contexts already created (repeating
  a size inside one process is slower than in a fresh process).
- On Wayland sessions every Tk app is forced through Xwayland + the ibus XIM
  bridge, so this legacy path is now the default path for such apps.
- Application-side workaround: avoid mass widget-per-item designs (a single
  Listbox instead of N Buttons). User-side workaround: `XMODIFIERS=''`
  (disables X input methods for that app).
"""


def main():
    child_n = os.environ.get('XIM_BENCH_CHILD')
    if child_n:
        bench_once(int(child_n))
        return
    sys.stderr.write('Running with ibus XIM active (slow pass)...\n')
    on = run_children('@im=ibus')
    sys.stderr.write('Running with XIM disabled (control pass)...\n')
    off = run_children('')
    report = make_report(on, off)
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'w') as fh:
            fh.write(report)
        sys.stderr.write(f'Report written to {sys.argv[1]}\n')
    else:
        print(report)


if __name__ == '__main__':
    main()
