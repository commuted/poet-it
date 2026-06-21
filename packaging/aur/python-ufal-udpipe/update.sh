#!/usr/bin/env bash
# Bump python-ufal-udpipe to the latest ufal.udpipe release on PyPI.
#
# Queries PyPI directly (version + sdist sha256, no download needed), rewrites
# pkgver/pkgrel/sha256sums in PKGBUILD, and regenerates .SRCINFO. Run on an Arch
# box so makepkg is available for the .SRCINFO step. Pairs with nvchecker
# (.nvchecker.toml) if you want change detection in CI, but works standalone.
set -euo pipefail
cd "$(dirname "$0")"

read -r ver sha < <(python - <<'PY'
import json, urllib.request
d = json.load(urllib.request.urlopen("https://pypi.org/pypi/ufal.udpipe/json"))
v = d["info"]["version"]
sha = next(f["digests"]["sha256"]
           for f in d["releases"][v] if f["packagetype"] == "sdist")
print(v, sha)
PY
)

cur=$(sed -n 's/^pkgver=//p' PKGBUILD)
if [ "$cur" = "$ver" ]; then
    echo "Already at $ver; nothing to do."
    exit 0
fi

echo "Bumping $cur -> $ver"
sed -i "s/^pkgver=.*/pkgver=$ver/"          PKGBUILD
sed -i "s/^pkgrel=.*/pkgrel=1/"             PKGBUILD
sed -i "s/^sha256sums=.*/sha256sums=('$sha')/" PKGBUILD

if command -v makepkg >/dev/null; then
    makepkg --printsrcinfo > .SRCINFO
    echo "Regenerated .SRCINFO"
else
    echo "WARNING: makepkg not found — regenerate .SRCINFO on an Arch host:" >&2
    echo "    makepkg --printsrcinfo > .SRCINFO" >&2
fi

echo "Review the diff, build-test (makepkg -s in a clean chroot), then:"
echo "    git commit -am 'upgpkg: ${ver}-1' && git push"
