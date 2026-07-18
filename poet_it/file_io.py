import json
import os
import tempfile


def meta_path(txt_path):
    return txt_path + ".meta"


def read_text_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines()


def read_meta_file(path):
    mp = meta_path(path)
    if not os.path.exists(mp):
        return None
    try:
        with open(mp, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_text_file(path, lines):
    content = list(lines)
    while content and not content[-1]:
        content.pop()
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(content) + "\n")
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise


def write_meta_file(path, meta):
    mp = meta_path(path)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(mp) or ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        os.replace(tmp, mp)
    except Exception:
        os.unlink(tmp)
        raise
