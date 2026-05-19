import pytest
from poetit.linguistics import Linguistics, word_at_cursor


# One shared instance — loading CMUDict and the rhyme dict is slow.
@pytest.fixture(scope="module")
def nlp():
    return Linguistics()


# ── word_at_cursor ────────────────────────────────────────────────────────────

class TestWordAtCursor:
    def test_cursor_inside_word(self):
        assert word_at_cursor("hello world", 7) == ("world", 6, 11)

    def test_cursor_at_word_start(self):
        assert word_at_cursor("hello world", 6) == ("world", 6, 11)

    def test_cursor_at_word_end(self):
        assert word_at_cursor("hello world", 11) == ("world", 6, 11)

    def test_cursor_at_string_start(self):
        assert word_at_cursor("hello world", 0) == ("hello", 0, 5)

    def test_cursor_on_space_returns_previous_word(self):
        word, start, end = word_at_cursor("hello world", 5)
        assert word == "hello"

    def test_empty_string(self):
        word, start, end = word_at_cursor("", 0)
        assert word == ""
        assert start == end

    def test_single_word(self):
        assert word_at_cursor("poetry", 3) == ("poetry", 0, 6)

    def test_cursor_clamps_beyond_end(self):
        word, start, end = word_at_cursor("hi", 100)
        assert word == "hi"


# ── line_syllables ────────────────────────────────────────────────────────────

class TestLineSyllables:
    def test_empty_string(self, nlp):
        assert nlp.line_syllables("") == 0

    def test_single_monosyllable(self, nlp):
        assert nlp.line_syllables("cat") == 1

    def test_single_monosyllable_the(self, nlp):
        assert nlp.line_syllables("the") == 1

    def test_two_syllables(self, nlp):
        assert nlp.line_syllables("hello") == 2

    def test_three_syllables(self, nlp):
        assert nlp.line_syllables("beautiful") == 3

    def test_classic_line(self, nlp):
        assert nlp.line_syllables("the cat sat on the mat") == 6

    def test_punctuation_ignored(self, nlp):
        assert nlp.line_syllables("hello, world!") == nlp.line_syllables("hello world")

    def test_numbers_ignored(self, nlp):
        assert nlp.line_syllables("42") == 0


# ── _cmu_syllables ────────────────────────────────────────────────────────────

class TestCmuSyllables:
    def test_known_word(self, nlp):
        assert nlp._cmu_syllables("cat") == 1

    def test_three_syllable_word(self, nlp):
        assert nlp._cmu_syllables("beautiful") == 3

    def test_unknown_word_returns_none(self, nlp):
        assert nlp._cmu_syllables("xyzzy") is None

    def test_case_insensitive(self, nlp):
        assert nlp._cmu_syllables("Cat") == nlp._cmu_syllables("cat")


# ── _rhyme_suffix ─────────────────────────────────────────────────────────────

class TestRhymeSuffix:
    def test_day(self, nlp):
        assert nlp._rhyme_suffix("day") == ("EY",)

    def test_night(self, nlp):
        assert nlp._rhyme_suffix("night") == ("AY", "T")

    def test_may_matches_day(self, nlp):
        assert nlp._rhyme_suffix("may") == nlp._rhyme_suffix("day")

    def test_unknown_word_returns_none(self, nlp):
        assert nlp._rhyme_suffix("xyzzy") is None


# ── compute_rhyme_scheme ──────────────────────────────────────────────────────

class TestComputeRhymeScheme:
    def test_empty(self, nlp):
        assert nlp.compute_rhyme_scheme([]) == []

    def test_blank_line(self, nlp):
        assert nlp.compute_rhyme_scheme([""]) == [""]

    def test_two_rhyming_lines(self, nlp):
        scheme = nlp.compute_rhyme_scheme(["a bright day", "come what may"])
        assert scheme == ["A", "A"]

    def test_non_rhyming_lines(self, nlp):
        scheme = nlp.compute_rhyme_scheme(["a bright day", "the dark night"])
        assert scheme[0] != scheme[1]

    def test_abab_pattern(self, nlp):
        lines = ["a bright day", "come what may", "the dark night", "a fading light"]
        assert nlp.compute_rhyme_scheme(lines) == ["A", "A", "B", "B"]

    def test_return_rhyme(self, nlp):
        lines = ["day", "say", "night", "day"]
        assert nlp.compute_rhyme_scheme(lines) == ["A", "A", "B", "A"]

    def test_all_different(self, nlp):
        lines = ["day", "night", "sea", "earth"]
        scheme = nlp.compute_rhyme_scheme(lines)
        assert len(set(scheme)) == 4

    def test_blank_lines_get_empty_label(self, nlp):
        scheme = nlp.compute_rhyme_scheme(["day", "", "may"])
        assert scheme[1] == ""
        assert scheme[0] == scheme[2]


# ── get_rhymes ────────────────────────────────────────────────────────────────

class TestGetRhymes:
    def test_known_word_returns_list(self, nlp):
        rhymes = nlp.get_rhymes("cat")
        assert isinstance(rhymes, list)
        assert len(rhymes) > 0

    def test_word_not_in_results(self, nlp):
        rhymes = nlp.get_rhymes("cat")
        assert "cat" not in [r.lower() for r in rhymes]

    def test_known_rhymes_present(self, nlp):
        rhymes = nlp.get_rhymes("cat")
        assert any(r.lower() in ("copycat", "pussycat", "tomcat") for r in rhymes)

    def test_unknown_word_returns_empty(self, nlp):
        assert nlp.get_rhymes("xyzzy") == []


# ── _is_function ──────────────────────────────────────────────────────────────

class TestIsFunction:
    def test_determiner_is_function(self, nlp):
        assert nlp._is_function("the", "DT") is True

    def test_modal_is_function(self, nlp):
        assert nlp._is_function("will", "MD") is True

    def test_auxiliary_is_function(self, nlp):
        assert nlp._is_function("is", "VBZ") is True

    def test_content_verb_is_not_function(self, nlp):
        assert nlp._is_function("run", "VB") is False

    def test_noun_is_not_function(self, nlp):
        assert nlp._is_function("river", "NN") is False

    def test_weak_dep_overrides_pos(self, nlp):
        assert nlp._is_function("in", "IN", dep="prep") is True

    def test_root_dep_not_function(self, nlp):
        assert nlp._is_function("sing", "VB", dep="ROOT") is False


# ── _syllabify_word ───────────────────────────────────────────────────────────

class TestSyllabifyWord:
    def test_monosyllable(self, nlp):
        result = nlp._syllabify_word("cat")
        assert len(result) == 1
        assert result[0][1] == 1   # primary stress

    def test_three_syllables(self, nlp):
        result = nlp._syllabify_word("beautiful")
        assert len(result) == 3
        stresses = [s for _, s in result]
        assert stresses[0] == 1    # primary stress on first syllable

    def test_function_word_gets_zero_stress(self, nlp):
        result = nlp._syllabify_word("the", is_function=True)
        assert all(s == 0 for _, s in result)

    def test_chunks_reassemble_to_word(self, nlp):
        word = "beautiful"
        result = nlp._syllabify_word(word)
        assert "".join(chunk for chunk, _ in result) == word


# ── check_spelling ────────────────────────────────────────────────────────────

class TestCheckSpelling:
    def test_correct_word_returns_true_no_suggestions(self, nlp):
        ok, suggestions = nlp.check_spelling("hello")
        assert ok is True
        assert suggestions == []

    def test_misspelled_word_returns_false(self, nlp):
        ok, _ = nlp.check_spelling("speling")
        assert ok is False

    def test_misspelled_word_has_suggestions(self, nlp):
        _, suggestions = nlp.check_spelling("speling")
        assert len(suggestions) > 0

    def test_suggestions_are_strings(self, nlp):
        _, suggestions = nlp.check_spelling("speling")
        assert all(isinstance(s, str) for s in suggestions)

    def test_misspelled_word_not_in_own_suggestions(self, nlp):
        _, suggestions = nlp.check_spelling("speling")
        assert "speling" not in suggestions

    def test_correct_suggestion_present(self, nlp):
        _, suggestions = nlp.check_spelling("speling")
        assert "spelling" in suggestions

    def test_case_insensitive_correct(self, nlp):
        ok_lower, _ = nlp.check_spelling("hello")
        ok_upper, _ = nlp.check_spelling("Hello")
        assert ok_lower is True
        assert ok_upper is True

    def test_case_insensitive_incorrect(self, nlp):
        ok_lower, _ = nlp.check_spelling("speling")
        ok_upper, _ = nlp.check_spelling("SPELING")
        assert ok_lower is False
        assert ok_upper is False

    def test_another_correct_word(self, nlp):
        ok, _ = nlp.check_spelling("poetry")
        assert ok is True

    def test_another_misspelled_word(self, nlp):
        ok, suggestions = nlp.check_spelling("potery")
        assert ok is False
        assert len(suggestions) > 0
