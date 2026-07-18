# Headless extraction of the rhyme-lookup path, for isolating the recent
# failure from the display stack (Wayland / mutter / Xwayland).
#
# _rhyme_click in app.py does, in order:
#   1. read the line text and cursor index from the focused Entry
#   2. word_at_cursor(text, cursor)          -> (word, ws, we)
#   3. Linguistics.get_rhymes(word)          -> list of candidate words
#   4. popups.show_word_list_popup(...)      -> GUI (not exercised here)
# Steps 1-3 are pure Python over bundled data files and need no display.
# If these tests pass while the app misbehaves, the fault is in step 4 or
# below it (Tk / XWayland / compositor), not in the lookup itself.
#
import os

import pytest

import poet_it.linguistics as ling

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_imports_this_repo():
    assert ling.__file__ == os.path.join(
        _REPO_ROOT, "poet_it", "linguistics.py"
    ), f"imported {ling.__file__} instead of this repo's copy"


@pytest.fixture(scope="module")
def nlp():
    return ling.Linguistics()


class TestDataFilesResolveAfterRename:
    """The package was renamed to poet_it; every loader falls back to {} /
    empty silently if its data file stops resolving, which surfaces in the
    UI as every rhyme lookup returning 'None found.'"""

    def test_cmudict_loaded(self, nlp):
        assert len(nlp._cmu) > 100_000

    def test_rhyme_dict_loaded(self, nlp):
        assert len(nlp._rhyme_dict) > 0


class TestRhymeClickPath:
    """Steps 2-3 of _rhyme_click, with realistic line text and cursor index."""

    def test_cursor_mid_word(self, nlp):
        text = "the silver moon"
        cursor = len(text) - 2          # inside "moon"
        word, ws, we = ling.word_at_cursor(text, cursor)
        assert word == "moon"
        rhymes = nlp.get_rhymes(word)
        assert rhymes, "no rhymes for a common word — lookup itself is broken"
        assert any(r.lower() == "soon" for r in rhymes)

    def test_cursor_after_line_end(self, nlp):
        # Typical flow: user typed a line, cursor sits past the last word.
        text = "a candle lost"
        word, ws, we = ling.word_at_cursor(text, len(text))
        assert word == "lost"
        assert nlp.get_rhymes(word)

    def test_results_are_popup_ready(self, nlp):
        """show_word_list_popup assumes a list of non-empty strings with no
        duplicates and without the query word itself."""
        rhymes = nlp.get_rhymes("day")
        assert isinstance(rhymes, list)
        assert all(isinstance(r, str) and r for r in rhymes)
        assert len(rhymes) == len(set(rhymes))
        assert "day" not in (r.lower() for r in rhymes)

    def test_unknown_word_gives_empty_list_not_error(self, nlp):
        assert nlp.get_rhymes("xyzzy") == []


class TestCorePathIsFast:
    """The reported symptom is an extreme delay ending in either a correct
    popup or the user giving up. Bound the entire non-GUI path at a fraction
    of a second so the delay can only be attributed to the popup / display
    stack. Measured on this machine: get_rhymes('saints') ~10 ms; the old
    Button-per-word popup takes 17 s for just 500 of its 3654 results."""

    def test_worst_case_lookup_under_500ms(self, nlp):
        import time
        t0 = time.perf_counter()
        for w in ("saints", "lost", "cat"):
            word, _, _ = ling.word_at_cursor(f"the {w}", 6)
            assert nlp.get_rhymes(word)
        assert time.perf_counter() - t0 < 0.5


class TestLargeResultLists:
    """The popup was rewritten (Buttons -> Listbox) because these exact lookups
    returned lists big enough to hang the old per-word-window design. Pin the
    magnitudes so a data or matching regression can't masquerade as a
    compositor problem."""

    def test_saints_is_large(self, nlp):
        assert len(nlp.get_rhymes("saints")) > 3000

    def test_lost_is_large(self, nlp):
        assert len(nlp.get_rhymes("lost")) > 1000
