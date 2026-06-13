"""Tests for Editor-level behaviour introduced with the spell-check toggle
and auto-scroll features.  These tests require a display server (tkinter).
"""
import pytest
import tkinter as tk

from poetit.app import Editor
from poetit.linguistics import Linguistics


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def nlp():
    return Linguistics()


@pytest.fixture(scope="module")
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture(scope="module")
def ed(root, nlp):
    return Editor(root, nlp)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_line(ed, row, text):
    te = ed.lines[row][0]
    te.delete(0, tk.END)
    te.insert(0, text)


# ---------------------------------------------------------------------------
# Spell toggle — on / off cycle
# ---------------------------------------------------------------------------

class TestSpellToggle:
    def test_initial_state_off(self, ed):
        assert ed._spell_var.get() is False
        assert ed._spell_underlines == {}

    def test_toggle_on_creates_underlines_for_all_rows(self, ed):
        ed._spell_var.set(True)
        ed._spell_activate()
        assert len(ed._spell_underlines) == len(ed.lines)

    def test_underline_widgets_are_canvases(self, ed):
        for te, uc in ed._spell_underlines.items():
            assert isinstance(uc, tk.Canvas)

    def test_toggle_off_removes_underlines(self, ed):
        ed._spell_deactivate()
        ed._spell_var.set(False)
        assert ed._spell_underlines == {}

    def test_toggle_on_off_idempotent(self, ed):
        for _ in range(3):
            ed._spell_var.set(True)
            ed._spell_activate()
            ed._spell_var.set(False)
            ed._spell_deactivate()
        assert ed._spell_underlines == {}


# ---------------------------------------------------------------------------
# _spell_scan_row
# ---------------------------------------------------------------------------

class TestSpellScanRow:
    def test_blank_line_has_no_errors(self, ed):
        _set_line(ed, 0, "")
        te = ed.lines[0][0]
        ed._spell_scan_row(te)
        assert ed._spell_errors.get(te, []) == []

    def test_correct_words_have_no_errors(self, ed):
        _set_line(ed, 0, "the cat sat")
        te = ed.lines[0][0]
        ed._spell_scan_row(te)
        assert ed._spell_errors.get(te, []) == []

    def test_misspelled_word_detected(self, ed):
        _set_line(ed, 0, "speling")
        te = ed.lines[0][0]
        ed._spell_scan_row(te)
        errors = ed._spell_errors.get(te, [])
        assert len(errors) == 1
        word, start, end, suggestions = errors[0]
        assert word == "speling"

    def test_error_span_matches_word_position(self, ed):
        _set_line(ed, 0, "good speling here")
        te = ed.lines[0][0]
        ed._spell_scan_row(te)
        errors = ed._spell_errors.get(te, [])
        assert len(errors) == 1
        word, start, end, suggestions = errors[0]
        assert start == 5
        assert end == 12

    def test_only_misspelled_words_in_errors(self, ed):
        _set_line(ed, 0, "correct speling correct")
        te = ed.lines[0][0]
        ed._spell_scan_row(te)
        errors = ed._spell_errors.get(te, [])
        words_in_error = [e[0] for e in errors]
        assert "correct" not in words_in_error
        assert "speling" in words_in_error

    def test_multiple_errors_detected(self, ed):
        _set_line(ed, 0, "speling erors here")
        te = ed.lines[0][0]
        ed._spell_scan_row(te)
        errors = ed._spell_errors.get(te, [])
        error_words = {e[0] for e in errors}
        assert "speling" in error_words
        assert "erors" in error_words

    def test_error_suggestions_non_empty(self, ed):
        _set_line(ed, 0, "speling")
        te = ed.lines[0][0]
        ed._spell_scan_row(te)
        errors = ed._spell_errors.get(te, [])
        assert errors
        _, _, _, suggestions = errors[0]
        assert len(suggestions) > 0

    def test_rescan_after_correction_clears_error(self, ed):
        _set_line(ed, 0, "speling")
        te = ed.lines[0][0]
        ed._spell_scan_row(te)
        assert len(ed._spell_errors.get(te, [])) == 1

        _set_line(ed, 0, "spelling")
        ed._spell_scan_row(te)
        assert ed._spell_errors.get(te, []) == []


# ---------------------------------------------------------------------------
# _ensure_row_visible — smoke tests (geometry checks need a rendered window)
# ---------------------------------------------------------------------------

class TestEnsureRowVisible:
    def test_valid_row_does_not_raise(self, ed):
        ed._ensure_row_visible(0)
        ed._ensure_row_visible(len(ed.lines) - 1)

    def test_out_of_range_rows_are_ignored(self, ed):
        ed._ensure_row_visible(-1)
        ed._ensure_row_visible(9999)

    def test_canvas_yview_is_valid_fraction_after_call(self, ed):
        ed._ensure_row_visible(0)
        top, bot = ed.canvas.yview()
        assert 0.0 <= top <= 1.0
        assert 0.0 <= bot <= 1.0
        assert top <= bot


# ---------------------------------------------------------------------------
# Diagram sentence selection (no display required)
# ---------------------------------------------------------------------------

class TestSentenceIndexAtOffset:
    @staticmethod
    def _doc(starts):
        """Stub doc whose sentences start at the given character offsets."""
        from types import SimpleNamespace as NS
        from poetit.app import _sentence_index_at_offset  # noqa: F401
        return NS(sentences=[NS(tokens=[NS(start_char=s)]) for s in starts])

    def test_offset_inside_each_sentence(self):
        from poetit.app import _sentence_index_at_offset
        doc = self._doc([0, 20, 41])
        assert _sentence_index_at_offset(doc, 5) == 0
        assert _sentence_index_at_offset(doc, 25) == 1
        assert _sentence_index_at_offset(doc, 60) == 2

    def test_offset_in_gap_selects_preceding_sentence(self):
        from poetit.app import _sentence_index_at_offset
        doc = self._doc([0, 20])
        assert _sentence_index_at_offset(doc, 19) == 0

    def test_offset_at_sentence_start(self):
        from poetit.app import _sentence_index_at_offset
        doc = self._doc([0, 20])
        assert _sentence_index_at_offset(doc, 20) == 1

    def test_offset_before_first_sentence_falls_back_to_first(self):
        from poetit.app import _sentence_index_at_offset
        doc = self._doc([3, 20])
        assert _sentence_index_at_offset(doc, 0) == 0

    def test_empty_sentence_tokens_are_skipped(self):
        from types import SimpleNamespace as NS
        from poetit.app import _sentence_index_at_offset
        doc = NS(sentences=[NS(tokens=[]), NS(tokens=[NS(start_char=0)])])
        assert _sentence_index_at_offset(doc, 5) == 1
