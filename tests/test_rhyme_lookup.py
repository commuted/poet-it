# Headless coverage of the rhyme-lookup path behind the Rhyme button.
#
# _rhyme_click in app.py does, in order:
#   1. read the line text and cursor index from the focused Entry
#   2. word_at_cursor(text, cursor)          -> (word, ws, we)
#   3. Linguistics.get_rhymes(word)          -> list of candidate words
#   4. popups.show_word_list_popup(...)      -> GUI (not exercised here)
# Steps 1-3 are pure Python over bundled data files and need no display.
# If these tests pass while the app misbehaves, the fault is in step 4 or
# below it (Tk / XWayland / compositor), not in the lookup itself.

import os
import sys

import pytest

import poetit.linguistics as ling

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_imports_this_repo_not_another_install():
    # An editable install of poetit elsewhere on the machine can shadow this
    # repo; every test below is meaningless if it does.
    assert ling.__file__ == os.path.join(_REPO_ROOT, "poetit", "linguistics.py"), (
        f"imported {ling.__file__} instead of this repo's copy"
    )


@pytest.fixture(scope="module")
def nlp():
    return ling.Linguistics()


class TestDataFilesResolve:
    """Both loaders fall back to {} silently if their data file stops
    resolving, which surfaces in the UI as every rhyme lookup returning
    'None found.'"""

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
    """The lookup feeds a popup the user is actively waiting on. Bound the
    entire non-GUI path at a fraction of a second so any perceptible delay
    can only be attributed to the popup / display stack. (The pre-Listbox
    popup took ~17 s to build just 500 of 'saints'' 3654 rows; the lookup
    itself is ~10 ms.)"""

    def test_worst_case_lookup_under_500ms(self, nlp):
        import time
        t0 = time.perf_counter()
        for w in ("saints", "lost", "cat"):
            word, _, _ = ling.word_at_cursor(f"the {w}", 6)
            assert nlp.get_rhymes(word)
        assert time.perf_counter() - t0 < 0.5


class TestLargeResultLists:
    """The popup must handle these magnitudes; pin them so a data or matching
    regression can't hide behind the GUI."""

    def test_saints_is_large(self, nlp):
        assert len(nlp.get_rhymes("saints")) > 3000

    def test_lost_is_large(self, nlp):
        assert len(nlp.get_rhymes("lost")) > 1000
