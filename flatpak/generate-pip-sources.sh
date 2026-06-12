#!/bin/sh
# Generates python3-requirements.json for offline Flatpak builds (required for Flathub).
# Run this once, and again whenever dependencies in requirements.txt change.
#
# Requires flatpak-pip-generator:
#   pip install flatpak-pip-generator
#
# torch handling: stanza depends on torch, but PyPI's torch is a ~4.5 GB CUDA
# build poetit can't use. flatpak-pip-generator omits torch (and the nvidia-*
# CUDA libraries) from its output on its own because they ship platform wheels
# only — you will see non-fatal "ERROR: Only platform wheels are available"
# lines for them. The manifest instead installs CPU-only torch FIRST via the
# hand-written python3-torch-cpu.json, which satisfies stanza's torch>=1.13
# requirement during the offline install. The post-processing step below
# removes the leftover pure-python cuda_* stub wheels (never installed, since
# torch+cpu does not depend on them) and fails if a torch wheel ever shows up
# in the generated output (it would shadow the CPU build).
set -e
cd "$(dirname "$0")"
python3 -m flatpak_pip_generator -r requirements.txt -o python3-requirements.json

python3 - <<'EOF'
import json, sys

with open('python3-requirements.json') as f:
    data = json.load(f)

for module in data['modules']:
    kept = []
    for src in module.get('sources', []):
        wheel = src.get('url', '').rsplit('/', 1)[-1]
        if wheel.startswith(('torch-', 'nvidia_', 'triton-')):
            sys.exit(f"error: {wheel} in generated sources — it would shadow "
                     "the CPU-only torch from python3-torch-cpu.json")
        if wheel.startswith('cuda_'):
            print(f"dropping dead CUDA stub source: {wheel}")
            continue
        kept.append(src)
    module['sources'] = kept

with open('python3-requirements.json', 'w') as f:
    json.dump(data, f, indent=4)
    f.write('\n')
EOF

echo "python3-requirements.json written."
