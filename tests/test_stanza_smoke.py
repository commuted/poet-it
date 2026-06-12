"""Smoke tests for the Stanza/PyTorch surface poetit depends on.

These tests guard the dependency scope documented at
``Linguistics._STANZA_PROCESSORS`` in poetit/linguistics.py, so that
``scripts/trim_nlp_footprint.py`` (which strips unused parts of stanza and
torch from an install) can be verified against the exact code paths poetit
exercises.
"""

import pytest

from poetit.linguistics import Linguistics, STANZA_AVAILABLE

# Two sentences; the contraction exercises the MWT processor.
SAMPLE_TEXT = "They don't know the poet's words. It rains softly tonight."


# ── Import surface (runs even where no models are downloaded) ────────────────

class TestImports:
    def test_torch_imports_and_computes(self):
        torch = pytest.importorskip("torch")
        assert torch.zeros(2).sum().item() == 0.0

    def test_stanza_pipeline_machinery_imports(self):
        pytest.importorskip("stanza")
        import stanza.pipeline.core      # noqa: F401  (Pipeline + processors)
        import stanza.resources.common   # noqa: F401  (download machinery)

    def test_transformers_not_required(self):
        """Stanza's pipeline machinery must import fine without transformers."""
        import subprocess
        import sys
        pytest.importorskip("stanza")
        code = (
            "import sys\n"
            "class B:\n"
            "    def find_module(self, name, path=None):\n"
            "        if name.split('.')[0] == 'transformers': return self\n"
            "    def load_module(self, name):\n"
            "        raise ImportError('blocked: ' + name)\n"
            "sys.meta_path.insert(0, B())\n"
            "import stanza.pipeline.core\n"
            "import stanza.resources.common\n"
        )
        subprocess.run([sys.executable, "-c", code], check=True)


# ── Full pipeline (skipped when the English models are not on disk) ──────────

@pytest.fixture(scope="module")
def stanza_doc():
    if not STANZA_AVAILABLE:
        pytest.skip("stanza not installed")
    import stanza
    try:
        nlp = stanza.Pipeline(
            'en',
            processors=Linguistics._STANZA_PROCESSORS,
            verbose=False,
            download_method=None,  # never hit the network in tests
        )
    except Exception as exc:
        pytest.skip(f"stanza English models not available offline: {exc}")
    return nlp(SAMPLE_TEXT)


class TestPipelineSurface:
    def test_sentences_split(self, stanza_doc):
        assert len(stanza_doc.sentences) == 2

    def test_mwt_expands_contractions(self, stanza_doc):
        words = [w.text for w in stanza_doc.sentences[0].words]
        # MWT splits "don't" into "do" + "n't"
        assert "do" in words and "n't" in words

    def test_consumed_word_attributes(self, stanza_doc):
        """Every attribute poetit reads must be populated on every word."""
        for sent in stanza_doc.sentences:
            for w in sent.words:
                assert isinstance(w.text, str) and w.text
                assert isinstance(w.id, int) and w.id >= 1
                assert isinstance(w.head, int) and w.head >= 0
                assert w.xpos
                assert w.upos
                assert w.deprel
                assert w.lemma

    def test_linguistics_adapter(self, stanza_doc):
        """End-to-end through poetit's own accessor."""
        nlp = Linguistics()
        doc = nlp.get_stanza_doc(SAMPLE_TEXT)
        if doc is None:
            pytest.skip("Linguistics could not load the stanza pipeline")
        words = [
            (w.text, w.xpos or 'NN', w.deprel or '')
            for sent in doc.sentences
            for w in sent.words
            if w.text.isalpha()
        ]
        assert words, "expected alphabetic words from the adapter"
