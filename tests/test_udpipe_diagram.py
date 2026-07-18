"""Smoke tests for the UDPipe dependency-parse backend that feeds the diagram.

The model (poet_it/data/english-ewt.udpipe, CC BY-SA 4.0) is bundled, so these
run wherever ufal.udpipe is installed.
"""
import pytest

from poet_it.linguistics import Linguistics, UDPIPE_AVAILABLE

pytestmark = pytest.mark.skipif(not UDPIPE_AVAILABLE, reason="ufal.udpipe not installed")

SAMPLE = "Shall I compare thee to a summer's day?\nThou art more lovely."


@pytest.fixture(scope="module")
def doc():
    d = Linguistics().get_diagram_doc(SAMPLE)
    if d is None:
        pytest.skip("UDPipe model could not be loaded")
    return d


def test_sentences_split(doc):
    assert len(doc.sentences) == 2


def test_word_surface_matches_renderer_expectations(doc):
    # popups._stanza_to_svg / show_diagram_popup read exactly these attributes.
    w = doc.sentences[0].words[0]
    for attr in ("id", "text", "upos", "xpos", "head", "deprel", "lemma"):
        assert hasattr(w, attr)
    assert isinstance(w.id, int)
    assert isinstance(w.head, int)


def test_each_sentence_has_a_root(doc):
    for sent in doc.sentences:
        assert any(w.head == 0 and w.deprel == "root" for w in sent.words)


def test_start_char_offsets_locate_sentences(doc):
    # Used by _sentence_index_at_offset to map a cursor to a sentence.
    starts = [s.tokens[0].start_char for s in doc.sentences]
    assert starts == sorted(starts)
    assert starts[0] == 0
    # Second sentence begins where "Thou" appears in the source text.
    assert starts[1] == SAMPLE.index("Thou")


def test_sentence_text_is_the_source_span(doc):
    assert doc.sentences[0].text.startswith("Shall I compare")
    assert "lovely" in doc.sentences[1].text


def test_capitalised_line_starts_do_not_split_a_sentence():
    # EBB, Sonnet 43: one sentence over three lines; "My" and "For" begin lines
    # without a preceding period and must NOT start new sentences.
    poem = ("I love thee to the depth and breadth and height\n"
            "My soul can reach, when feeling out of sight\n"
            "For the ends of being and ideal grace.")
    d = Linguistics().get_diagram_doc(poem)
    if d is None:
        pytest.skip("UDPipe model could not be loaded")
    assert len(d.sentences) == 1
    forms = [w.text for w in d.sentences[0].words]
    assert "My" in forms and "For" in forms      # all three lines in one parse
    assert any(w.head == 0 and w.deprel == "root" for w in d.sentences[0].words)
