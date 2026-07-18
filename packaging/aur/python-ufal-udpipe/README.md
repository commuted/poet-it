# python-ufal-udpipe (AUR packaging)

A ready-to-submit AUR package for [`ufal.udpipe`](https://pypi.org/project/ufal.udpipe/),
the Python bindings for [UDPipe](https://ufal.mff.cuni.cz/udpipe) (tokenization,
tagging, lemmatization, and dependency parsing). poet-it uses it as the default,
bundled-model dependency-diagram backend, but it is a generic, standalone binding
useful to any package — hence offered here as its own AUR package rather than
vendored.

There is currently **no `python-ufal-udpipe` in the AUR**. These files exist so a
maintainer can drop them into a fresh AUR repo and wire them into an automated
update flow with little effort.

## What's here

| File | Purpose |
|---|---|
| `PKGBUILD` | Builds from the official PyPI **sdist** (which ships the pre-generated SWIG wrapper, so no `swig` is needed — only a C++ compiler). |
| `.SRCINFO` | Generated metadata the AUR requires. Regenerate with `makepkg --printsrcinfo > .SRCINFO`. |
| `.nvchecker.toml` | Watches the PyPI release for new versions. |
| `update.sh` | Bumps `pkgver`/`pkgrel`/`sha256sums` from PyPI and regenerates `.SRCINFO`. |

## Facts (verified against PyPI / the sdist)

- **Version:** 1.4.0.1 (the *bindings* version; it differs from UDPipe core, so track PyPI, not the GitHub tags).
- **License:** MPL-2.0.
- **`arch`:** `x86_64`, `aarch64` — it compiles a C++/SWIG extension, so not `any`.
- **Runtime deps:** just `python`. No PyTorch, no NLTK.

## Build / test locally

```bash
makepkg -si              # build and install
# or in a clean chroot for release validation:
extra-x86_64-build
```

## Submitting to the AUR

```bash
git clone ssh://aur@aur.archlinux.org/python-ufal-udpipe.git
cp PKGBUILD .SRCINFO python-ufal-udpipe/
cd python-ufal-udpipe
git add PKGBUILD .SRCINFO
git commit -m 'Initial import: python-ufal-udpipe 1.4.0.1'
git push
```

(Keep `.nvchecker.toml` and `update.sh` in your own maintenance repo — the AUR
repo only needs `PKGBUILD` and `.SRCINFO`.)

## Automated updates

The standard flow, which these files plug into:

1. **nvchecker** reads `.nvchecker.toml` and reports the newest PyPI version (it
   only *detects* — it doesn't edit or push).
2. **`./update.sh`** applies it: rewrites `pkgver`, resets `pkgrel=1`, refreshes
   `sha256sums` (pulled straight from PyPI's digest), and regenerates `.SRCINFO`.
3. You review, build-test, then `git commit` + `git push` to the AUR remote — or
   let CI do it (e.g. the `KSXGitHub/github-actions-deploy-aur` action) holding
   the AUR SSH key. The AUR runs no CI of its own, so the push must come from you
   or an external runner.
