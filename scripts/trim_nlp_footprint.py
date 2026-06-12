#!/usr/bin/env python3
"""Trim unused Stanza and PyTorch files from an installed site-packages.

poetit uses exactly one Stanza pipeline — Pipeline('en',
processors='tokenize,mwt,pos,lemma,depparse') — running CPU-only torch
inference (see Linguistics._STANZA_PROCESSORS in poetit/linguistics.py).
The deny-list below was derived by tracing every module that pipeline
loads (including the stanza.download() code path) and deleting only
subtrees containing none of them.

Two hard constraints shape the list:
  * stanza/pipeline/core.py eagerly imports EVERY processor family (ner,
    constituency, coref, sentiment, langid) plus stanza.server.* — so
    stanza model packages must stay even though poetit never runs them.
  * importing torch touches ~1000 python modules across nearly all of its
    subpackages — so only non-code assets (C++ headers, bundled binaries,
    type stubs, cmake files) are removed from torch. Never delete torch
    python modules.

To re-derive the deny-list after a stanza/torch upgrade: run the pipeline
above under a fresh interpreter, dump sorted(sys.modules), and check each
denied path still contains no loaded module. A missing *required* path
below means the upstream layout changed — re-trace instead of ignoring.

Usage:
    python3 scripts/trim_nlp_footprint.py --site-packages PATH
            [--dry-run] [--expect-cpu] [--keep-pyi]

This script is stdlib-only so it can run inside the flatpak-builder
sandbox as a post-install build command, or against any local venv.
"""

import argparse
import glob
import os
import shutil
import sys

REQUIRED = "required"
OPTIONAL = "optional"

# (relative path or glob under site-packages, required|optional)
DENY_LIST = [
    # ── stanza: test suites, demo assets, dataset/training prep tools ──
    ("stanza/tests", REQUIRED),
    ("stanza/pipeline/demo", REQUIRED),
    ("stanza/utils/visualization", REQUIRED),
    ("stanza/utils/charlm", REQUIRED),
    ("stanza/utils/ner", REQUIRED),
    ("stanza/utils/constituency", REQUIRED),
    ("stanza/utils/languages", REQUIRED),
    ("stanza/utils/pretrain", REQUIRED),
    ("stanza/utils/lemma", REQUIRED),
    ("stanza/utils/datasets/constituency", REQUIRED),
    ("stanza/utils/datasets/coref", REQUIRED),
    ("stanza/utils/datasets/ner", REQUIRED),
    ("stanza/utils/datasets/pos", REQUIRED),
    ("stanza/utils/datasets/pretrain", REQUIRED),
    ("stanza/utils/datasets/sentiment", REQUIRED),
    ("stanza/utils/datasets/tokenization", REQUIRED),
    ("stanza/utils/datasets/vietnamese", OPTIONAL),
    # ── dulwich: test suite, GCS backend, CLI entry point ──
    # (porcelain lazily imports many sibling modules per command, so only
    # whole subpackages and the standalone CLI are safe to remove)
    ("dulwich/tests", REQUIRED),
    ("dulwich/cloud", REQUIRED),
    ("dulwich/cli.py", OPTIONAL),
    # ── torch: non-code assets only ──
    ("torch/include", REQUIRED),         # C++ headers (extension builds only)
    ("torch/share", OPTIONAL),           # cmake config
    ("torch/bin/protoc", OPTIONAL),      # bundled protobuf compiler
    ("torch/bin/protoc-*", OPTIONAL),
    ("torch/bin/ptxas", OPTIONAL),       # CUDA tool; absent in +cpu wheels
    ("functorch", OPTIONAL),             # legacy shim package, never imported
]

# Type stubs: only useful to IDEs/type checkers, skipped with --keep-pyi.
PYI_GLOBS = ["torch/**/*.pyi", "torchgen/**/*.pyi"]

# With --expect-cpu, any of these existing means a CUDA build slipped in.
CUDA_MARKERS = [
    "nvidia",
    "triton",
    "cuda",
    "torch/lib/libtorch_cuda*",
    "torch/lib/libc10_cuda*",
]


def tree_size(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def fmt(nbytes):
    return f"{nbytes / 1e6:,.1f} MB"


def remove(path, dry_run):
    if dry_run:
        return
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def prune_orphan_pycache(pkg_root, dry_run):
    """Drop __pycache__ entries whose source .py no longer exists."""
    freed = 0
    for root, dirs, files in os.walk(pkg_root):
        if os.path.basename(root) != "__pycache__":
            continue
        dirs[:] = []
        src_dir = os.path.dirname(root)
        for f in files:
            stem = f.split(".")[0]
            if not os.path.exists(os.path.join(src_dir, stem + ".py")):
                p = os.path.join(root, f)
                freed += os.path.getsize(p)
                remove(p, dry_run)
    return freed


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--site-packages", required=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be removed without deleting")
    ap.add_argument("--expect-cpu", action="store_true",
                    help="fail if CUDA packages/libraries are present")
    ap.add_argument("--keep-pyi", action="store_true",
                    help="keep .pyi type stubs (recommended for dev venvs)")
    args = ap.parse_args()

    sp = os.path.abspath(args.site_packages)
    missing = [p for p in ("stanza", "torch", "dulwich")
               if not os.path.isdir(os.path.join(sp, p))]
    if missing:
        sys.exit(f"error: {sp} does not contain: {', '.join(missing)}")

    if args.expect_cpu:
        offenders = []
        for marker in CUDA_MARKERS:
            offenders += glob.glob(os.path.join(sp, marker))
        if offenders:
            for o in offenders:
                print(f"CUDA artifact present: {o}", file=sys.stderr)
            sys.exit("error: --expect-cpu set but CUDA artifacts found; "
                     "install torch from https://download.pytorch.org/whl/cpu")

    before = {pkg: tree_size(os.path.join(sp, pkg))
              for pkg in ("stanza", "torch")}

    failures = []
    freed = 0
    targets = list(DENY_LIST)
    if not args.keep_pyi:
        targets += [(g, OPTIONAL) for g in PYI_GLOBS]

    for rel, level in targets:
        matches = glob.glob(os.path.join(sp, rel), recursive=True)
        if not matches:
            if level == REQUIRED:
                failures.append(rel)
                print(f"MISSING (required): {rel}", file=sys.stderr)
            continue
        for path in matches:
            size = tree_size(path)
            freed += size
            print(f"{'would remove' if args.dry_run else 'removing':>12}  "
                  f"{fmt(size):>10}  {os.path.relpath(path, sp)}")
            remove(path, args.dry_run)

    for pkg in ("stanza", "torch"):
        freed += prune_orphan_pycache(os.path.join(sp, pkg), args.dry_run)

    print()
    for pkg in ("stanza", "torch"):
        after = tree_size(os.path.join(sp, pkg))
        print(f"{pkg:>8}: {fmt(before[pkg])} -> {fmt(after)}")
    print(f"{'total':>8}: freed {fmt(freed)}"
          f"{' (dry run — nothing deleted)' if args.dry_run else ''}")

    if failures:
        sys.exit(
            "error: expected deny-list paths missing — the stanza/torch "
            "layout changed; re-trace the pipeline (see module docstring) "
            "and update DENY_LIST: " + ", ".join(failures)
        )


if __name__ == "__main__":
    main()
