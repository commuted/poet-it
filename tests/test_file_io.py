import json
import os
import pytest
import tempfile

from poetit import file_io


# ── meta_path ────────────────────────────────────────────────────────────────

def test_meta_path_appends_suffix():
    assert file_io.meta_path("/foo/bar.txt") == "/foo/bar.txt.meta"

def test_meta_path_any_extension():
    assert file_io.meta_path("/a/b.poem") == "/a/b.poem.meta"


# ── write_text_file / read_text_file ─────────────────────────────────────────

def test_roundtrip_basic(tmp_path):
    p = str(tmp_path / "poem.txt")
    lines = ["roses are red", "violets are blue"]
    file_io.write_text_file(p, lines)
    assert file_io.read_text_file(p) == lines

def test_write_strips_trailing_blanks(tmp_path):
    p = str(tmp_path / "poem.txt")
    file_io.write_text_file(p, ["hello", "", ""])
    assert file_io.read_text_file(p) == ["hello"]

def test_write_all_blank_produces_single_newline(tmp_path):
    # All blanks stripped → writes a bare "\n"; splitlines gives ['']
    p = str(tmp_path / "poem.txt")
    file_io.write_text_file(p, ["", "", ""])
    assert file_io.read_text_file(p) == [""]

def test_write_preserves_internal_blanks(tmp_path):
    p = str(tmp_path / "poem.txt")
    lines = ["line one", "", "line three"]
    file_io.write_text_file(p, lines)
    assert file_io.read_text_file(p) == lines

def test_write_is_utf8(tmp_path):
    p = str(tmp_path / "poem.txt")
    file_io.write_text_file(p, ["café", "naïve"])
    assert file_io.read_text_file(p) == ["café", "naïve"]

def test_write_uses_atomic_replace(tmp_path):
    p = str(tmp_path / "poem.txt")
    file_io.write_text_file(p, ["first"])
    file_io.write_text_file(p, ["second"])
    assert file_io.read_text_file(p) == ["second"]


# ── write_meta_file / read_meta_file ─────────────────────────────────────────

def test_meta_roundtrip(tmp_path):
    base = str(tmp_path / "poem.txt")
    meta = {"font": "Courier", "size": 12}
    file_io.write_meta_file(base, meta)
    assert file_io.read_meta_file(base) == meta

def test_read_meta_missing_returns_none(tmp_path):
    base = str(tmp_path / "nonexistent.txt")
    assert file_io.read_meta_file(base) is None

def test_meta_roundtrip_nested(tmp_path):
    base = str(tmp_path / "poem.txt")
    meta = {"runs": [{"font": "Courier", "size": 12, "len": 5}]}
    file_io.write_meta_file(base, meta)
    assert file_io.read_meta_file(base) == meta
