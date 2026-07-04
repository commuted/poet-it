import json
import os
import re
import threading

import nltk
from nltk import word_tokenize
from nltk.tokenize import SyllableTokenizer

try:
    import prosodic as _prosodic
    _PROSODIC_AVAILABLE = True
except ImportError:
    _PROSODIC_AVAILABLE = False

try:
    import stanza as _stanza
    STANZA_AVAILABLE = True
except ImportError:
    STANZA_AVAILABLE = False

try:
    from ufal.udpipe import (Model as _UDModel, Sentence as _UDSentence,
                             ProcessingError as _UDError)
    UDPIPE_AVAILABLE = True
except ImportError:
    UDPIPE_AVAILABLE = False

try:
    from spellchecker import SpellChecker as _SpellChecker
    SPELLCHECKER_AVAILABLE = True
except ImportError:
    SPELLCHECKER_AVAILABLE = False

SEP_DOT = "·"

# Lightweight stand-ins mirroring the slice of Stanza's parsed-doc surface that
# the diagram code (popups._stanza_to_svg, show_diagram_popup) and the cursor →
# sentence mapping (_sentence_index_at_offset in app.py) consume. Building these
# from UDPipe output lets the renderer stay backend-agnostic.
class _DiagramWord:
    __slots__ = ('id', 'text', 'lemma', 'upos', 'xpos', 'head', 'deprel')

class _DiagramToken:
    __slots__ = ('start_char',)
    def __init__(self, start_char):
        self.start_char = start_char

class _DiagramSentence:
    __slots__ = ('words', 'tokens', 'text')

class _DiagramDoc:
    __slots__ = ('sentences',)
    def __init__(self, sentences):
        self.sentences = sentences

# Trailing enclitics for English contractions and possessives, used to accept
# apostrophe forms (e.g. "children's") whose stem is a known word.
_CONTRACTION_CLITICS = frozenset({"s", "t", "d", "m", "re", "ve", "ll"})

# Archaic / poetic vocabulary the general dictionary lacks, seeded into the
# spell checker so it does not underline them. Written as the word tokenizer
# yields them: a leading apostrophe is dropped ("'tis" -> "tis"), while an
# internal one is kept ("o'er", "ne'er").
_POETIC_WORDS = frozenset({
    "tis", "twas", "twere", "twill", "twixt", "gainst", "neath", "mongst",
    "o'er", "ne'er", "e'er", "e'en",
    "ere", "oft", "ope", "whilst", "amongst", "betwixt", "hither", "thither",
    "whither", "yon", "yonder", "morn", "eve", "wrought", "clad",
    "thee", "thou", "thy", "thine", "ye", "hath", "doth", "dost", "hast",
    "wast", "wert", "shalt", "wilt", "canst", "didst", "couldst", "wouldst",
    "shouldst", "mayst", "prithee", "forsooth", "verily",
})

_WEAK_DEPS = frozenset({
    # Universal Dependencies (Stanza)
    'aux', 'aux:pass', 'det', 'mark', 'cc', 'case', 'expl', 'cop',
    # Stanford / spaCy aliases kept for fallback compatibility
    'auxpass', 'prep',
})

_FUNCTION_POS = frozenset({
    "CC", "DT", "EX", "IN", "MD", "PDT", "POS",
    "PRP", "PRP$", "RP", "TO", "WDT", "WP", "WP$", "WRB",
})

_WEAK_WORDS = frozenset({'so', 'too', 'very', 'quite', 'rather', 'just'})

_AUXILIARIES = frozenset({
    'be', 'is', 'am', 'are', 'was', 'were', 'been', 'being',
    'have', 'has', 'had', 'having',
    'do', 'does', 'did',
    'will', 'would', 'shall', 'should',
    'can', 'could', 'may', 'might', 'must',
    'hath', 'doth', 'wilt', 'shalt', 'canst',
    'wouldst', 'shouldst', 'dost',
})

_DO_SUPPORT = frozenset({'do', 'does', 'did', 'doth', 'dost'})
_HAVE_AUX   = frozenset({'have', 'has', 'had', 'having', 'hath', 'hadst'})

_NLTK_PACKAGES = [
    ("tokenizers/punkt", "punkt_tab"),
    ("corpora/words", "words"),
    ("taggers/averaged_perceptron_tagger", "averaged_perceptron_tagger"),
    ("taggers/averaged_perceptron_tagger_eng", "averaged_perceptron_tagger_eng"),
]


def _inject_bundled_nltk_data():
    """Add the package's bundled corpora directory to NLTK's search path."""
    from importlib.resources import files
    try:
        data_dir = str(files('poetit').joinpath('data'))
    except Exception:
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    if data_dir not in nltk.data.path:
        nltk.data.path.insert(0, data_dir)


def _ensure_nltk_data():
    _inject_bundled_nltk_data()
    for path, name in _NLTK_PACKAGES:
        try:
            nltk.data.find(path)
        except LookupError:
            try:
                nltk.download(name, quiet=True)
            except Exception:
                pass


def _read_data(filename):
    from importlib.resources import files
    try:
        return files('poetit').joinpath('data', filename).read_text(encoding='utf-8')
    except Exception:
        pass
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(here, 'data', filename)
    if os.path.exists(candidate):
        with open(candidate, encoding='utf-8') as fh:
            return fh.read()
    return None


def _load_cmudict():
    text = _read_data('cmudict.dict')
    if not text:
        return {}
    result = {}
    for line in text.splitlines():
        if line.startswith(';;;') or not line.strip():
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        word = parts[0].lower()
        phonemes = parts[2:]   # parts[1] is the variant number
        result.setdefault(word, []).append(phonemes)
    return result


def word_at_cursor(text, idx):
    idx = max(0, min(idx, len(text)))
    start = idx
    while start > 0 and text[start - 1].isalpha():
        start -= 1
    end = idx
    while end < len(text) and text[end].isalpha():
        end += 1
    if start < end:
        return text[start:end], start, end
    end = idx
    while end > 0 and not text[end - 1].isalpha():
        end -= 1
    start = end
    while start > 0 and text[start - 1].isalpha():
        start -= 1
    return text[start:end], start, end


def _levenshtein(a, b):
    la, lb = len(a), len(b)
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        for j in range(1, lb + 1):
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1]))
        prev = curr
    return prev[lb]


class Linguistics:
    def __init__(self):
        _ensure_nltk_data()
        self._cmu        = _load_cmudict()
        self._syl_tok    = SyllableTokenizer()
        self._rhyme_dict = self._load_rhyme_dict()
        self._thesaurus_lock     = threading.Lock()
        self._thesaurus          = None
        self._thesaurus_loading  = False
        self._stanza_lock    = threading.Lock()
        self._stanza_nlp     = None
        self._stanza_loading = False
        self._stanza_failed  = False
        self._udpipe_lock    = threading.Lock()
        self._udpipe_model   = None
        self._udpipe_failed  = False
        self._spell              = _SpellChecker() if SPELLCHECKER_AVAILABLE else None
        if self._spell is not None:
            self._spell.word_frequency.load_words(_POETIC_WORDS)
        self._words_corpus       = None   # NLTK words corpus, built on first use

    def start_background_loads(self):
        # Warm whichever diagram backend will actually be used: Stanza (quality
        # mode) if its model is on disk, otherwise the bundled UDPipe model.
        if STANZA_AVAILABLE and self._stanza_model_on_disk():
            threading.Thread(target=self._ensure_stanza_pipeline, daemon=True).start()
        elif UDPIPE_AVAILABLE:
            threading.Thread(target=self._ensure_udpipe_model, daemon=True).start()
        threading.Thread(target=self._load_thesaurus_background, daemon=True).start()
        if self._spell is not None:
            threading.Thread(target=self._warm_spell_backups, daemon=True).start()

    def _warm_spell_backups(self):
        """Preload the backup spell dictionaries off the UI thread; the first
        WordNet lookup otherwise stalls the first spell scan by ~2 s."""
        try:
            self._ensure_words_corpus()
            self._wordnet_knows('poem')
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Syllable counting
    # ------------------------------------------------------------------ #

    def _best_cmu_entry(self, word):
        entries = self._cmu.get(word.lower())
        if not entries:
            return None
        if len(entries) == 1:
            return entries[0]
        counts = [sum(1 for ph in e if ph[-1].isdigit()) for e in entries]
        if len(set(counts)) == 1:
            return entries[0]
        best_idx = min(range(len(counts)), key=lambda i: (counts[i], i))
        return entries[best_idx]

    def _cmu_syllables(self, word):
        entry = self._best_cmu_entry(word)
        if entry is not None:
            return sum(1 for ph in entry if ph[-1].isdigit())
        return None

    def _fallback_syllables(self, word):
        if not word:
            return 0
        return max(1, len(self._syl_tok.tokenize(word.lower())))

    def line_syllables(self, text):
        total = 0
        for token in word_tokenize(text):
            if not any(ch.isalpha() for ch in token):
                continue
            n = self._cmu_syllables(token)
            if n is None:
                n = self._fallback_syllables(token)
            total += n
        return total

    # ------------------------------------------------------------------ #
    # Rhyme dictionary and scheme
    # ------------------------------------------------------------------ #

    def _load_rhyme_dict(self):
        content = _read_data('rdict.json')
        if not content:
            return {}
        try:
            start = content.index('var rhdict = ') + len('var rhdict = ')
            end   = content.index('\nvar spdict = ')
            return json.loads(content[start:end].rstrip(';\n '))
        except (ValueError, json.JSONDecodeError):
            return {}

    def _rhyme_suffix(self, word):
        entry = self._best_cmu_entry(word)
        if not entry:
            return None
        for i in range(len(entry) - 1, -1, -1):
            if entry[i][-1].isdigit():
                return tuple(re.sub(r'\d', '', ph) for ph in entry[i:])
        return None

    def get_rhymes(self, word):
        if not self._rhyme_dict:
            return []
        entries = self._cmu.get(word.lower())
        if not entries:
            return []
        phonemes = [re.sub(r'\d', '', ph) for ph in entries[0]]
        rev = list(reversed(phonemes))
        key = rev[0]
        if key not in self._rhyme_dict:
            return []
        results = []
        for s in range(len(rev) - 1, 0, -1):
            st  = ' '.join(rev[:s + 1])
            stl = len(st)
            for entry in self._rhyme_dict[key]:
                if entry[:stl] == st:
                    results.append(entry.split()[-1])
        seen, unique = set(), []
        for w in results:
            if w not in seen and w.lower() != word.lower():
                seen.add(w)
                unique.append(w)
        return unique

    def compute_rhyme_scheme(self, texts):
        scheme, anchors, next_idx = [], [], 0
        for text in texts:
            words_in = re.findall(r'[A-Za-z]+', text)
            if not words_in:
                scheme.append('')
                continue
            suffix = self._rhyme_suffix(words_in[-1])
            letter = None
            if suffix:
                for anchor_suffix, anchor_letter in anchors:
                    if anchor_suffix == suffix:
                        letter = anchor_letter
                        break
            if letter is None:
                if next_idx < 26:
                    letter = chr(ord('A') + next_idx)
                elif next_idx < 52:
                    letter = chr(ord('a') + next_idx - 26)
                else:
                    letter = '?'
                next_idx += 1
                if suffix:
                    anchors.append((suffix, letter))
            scheme.append(letter)
        return scheme

    # ------------------------------------------------------------------ #
    # Thesaurus
    # ------------------------------------------------------------------ #

    def _load_thesaurus_background(self):
        with self._thesaurus_lock:
            if self._thesaurus is not None or self._thesaurus_loading:
                return
            self._thesaurus_loading = True
        try:
            result = self._load_thesaurus()
        except Exception:
            result = {}
        with self._thesaurus_lock:
            self._thesaurus = result
            self._thesaurus_loading = False

    def _load_thesaurus(self):
        raw = _read_data('th_en_US_new.json')
        if not raw:
            return {}
        raw = raw.strip()
        if raw.startswith('module.exports = '):
            raw = raw[len('module.exports = '):]
        if raw.endswith(';'):
            raw = raw[:-1]
        return json.loads(raw)

    def get_thesaurus(self, word):
        with self._thesaurus_lock:
            thesaurus = self._thesaurus
            if thesaurus is None and not self._thesaurus_loading:
                self._thesaurus_loading = True
                do_load = True
            else:
                do_load = False
        if do_load:
            try:
                result = self._load_thesaurus()
            except Exception:
                result = {}
            with self._thesaurus_lock:
                self._thesaurus = result
                self._thesaurus_loading = False
            thesaurus = result
        if not thesaurus:
            return []
        key  = word.lower()
        syns = thesaurus.get(key, [])
        seen, result = {key}, []
        for s in syns:
            sl = s.lower()
            if sl not in seen:
                seen.add(sl)
                result.append(s)
        return result

    # ------------------------------------------------------------------ #
    # Spell checking
    # ------------------------------------------------------------------ #

    def _ensure_words_corpus(self):
        if self._words_corpus is None:
            try:
                from nltk.corpus import words as _words
                self._words_corpus = frozenset(w.lower() for w in _words.words())
            except Exception:
                self._words_corpus = frozenset()
        return self._words_corpus

    @staticmethod
    def _wordnet_knows(word):
        try:
            from nltk.corpus import wordnet as _wn
            return bool(_wn.synsets(word))
        except Exception:
            return False

    def _thesaurus_knows(self, word):
        # Consult only if the background load has finished; blocking the UI
        # thread on a multi-megabyte JSON parse is worse than a rare miss.
        with self._thesaurus_lock:
            thesaurus = self._thesaurus
        return bool(thesaurus) and word in thesaurus

    def _known_to_backup_dicts(self, lower):
        """Fallback lookup for words the primary dictionary rejects.

        Cascades through the other bundled word lists — the CMU pronouncing
        dictionary, the NLTK words corpus, WordNet, and the thesaurus — so a
        valid-but-rare word missing from pyspellchecker's frequency list is
        not underlined. A hit is fed back into the primary dictionary so the
        word takes the fast path on every later scan.
        """
        ascii_form = lower.replace('’', "'")
        known = (
            ascii_form in self._cmu
            or ascii_form in self._ensure_words_corpus()
            or self._wordnet_knows(ascii_form)
            or self._thesaurus_knows(ascii_form)
        )
        if known:
            self._spell.word_frequency.load_words([lower])
        return known

    def misspelled_words(self, text):
        """Return the set of lowercase unknown words found in text."""
        if self._spell is None:
            return set()
        words = re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)*", text)
        if not words:
            return set()
        unknown = self._spell.unknown([w.lower() for w in words])
        return {w for w in unknown if not self._known_to_backup_dicts(w)}

    def check_spelling(self, word):
        """Return (is_correct, [suggestions]) for word.

        Suggestions are sorted by edit distance (closest first) then by
        frequency descending within each edit-distance tier.
        """
        if self._spell is None:
            return True, []
        lower = word.lower()
        if not self._spell.unknown([lower]):
            return True, []
        if self._known_to_backup_dicts(lower):
            return True, []
        # Contractions and possessives the dictionary may not list as a unit
        # (e.g. "children's"): accept when the stem is a known word and the
        # trailing piece is a standard English enclitic. Common forms such as
        # "isn't" or "dog's" are already in the dictionary and returned above.
        if "'" in lower or "’" in lower:
            parts = re.split(r"['’]", lower)
            if (len(parts) == 2 and parts[0]
                    and parts[1] in _CONTRACTION_CLITICS
                    and (not self._spell.unknown([parts[0]])
                         or self._known_to_backup_dicts(parts[0]))):
                return True, []
        candidates = self._spell.candidates(lower) or set()
        candidates.discard(lower)
        ranked = sorted(
            candidates,
            key=lambda w: (_levenshtein(lower, w), -self._spell.word_usage_frequency(w)),
        )
        return False, ranked

    # ------------------------------------------------------------------ #
    # Stanza
    # ------------------------------------------------------------------ #

    # The complete Stanza surface poetit consumes: this processor list, plus
    # doc.sentences[*].words[*] attributes text/id/head/xpos/upos/deprel/lemma
    # and doc.sentences[*] attributes text and tokens[*].start_char (read
    # here, in app.py, and in popups.py). scripts/trim_nlp_footprint.py and
    # tests/test_stanza_smoke.py rely on this scope staying this narrow.
    _STANZA_PROCESSORS = 'tokenize,mwt,pos,lemma,depparse'

    # Pin the EWT-only model (CC BY-SA 4.0). Stanza's default English package is
    # a combined model that includes GUM (CC BY-NC-SA 4.0), whose non-commercial
    # term is incompatible with poetit's MIT licensing.
    _STANZA_PACKAGE = 'ewt'

    @staticmethod
    def _stanza_model_on_disk():
        """Return True if the Stanza English model files are present on disk."""
        tokenize_dir = os.path.join(
            os.path.expanduser('~'), 'stanza_resources', 'en', 'tokenize'
        )
        try:
            return bool(os.listdir(tokenize_dir))
        except OSError:
            return False

    def _ensure_stanza_pipeline(self):
        """Load the Stanza ewt pipeline from disk; never downloads. Returns the
        pipeline, or None if Stanza or its model is absent (the diagram then
        falls back to UDPipe). tokenize_no_ssplit keeps each Punkt span we feed
        it as a single sentence rather than re-segmenting it."""
        if not STANZA_AVAILABLE:
            return None
        with self._stanza_lock:
            if self._stanza_nlp is not None or self._stanza_failed or self._stanza_loading:
                return self._stanza_nlp
            self._stanza_loading = True
        pipeline = None
        if self._stanza_model_on_disk():
            try:
                pipeline = _stanza.Pipeline(
                    'en',
                    package=self._STANZA_PACKAGE,
                    processors=self._STANZA_PROCESSORS,
                    tokenize_no_ssplit=True,
                    download_method=None,
                    verbose=False,
                )
            except Exception:
                pipeline = None
        with self._stanza_lock:
            self._stanza_nlp = pipeline
            self._stanza_failed = pipeline is None
            self._stanza_loading = False
        return pipeline

    @staticmethod
    def _stanza_words(pipeline, seg):
        doc = pipeline(seg)
        if not doc.sentences:
            return None
        out = []
        for sw in doc.sentences[0].words:   # tokenize_no_ssplit => one sentence
            w = _DiagramWord()
            w.id, w.text, w.lemma = sw.id, sw.text, sw.lemma
            w.upos, w.xpos = sw.upos, sw.xpos
            w.head, w.deprel = sw.head, sw.deprel
            out.append(w)
        return out

    # ------------------------------------------------------------------ #
    # Dependency parsing for the diagram (UDPipe default, Stanza if present)
    # ------------------------------------------------------------------ #

    # English EWT model, CC BY-SA 4.0 (commercial use allowed) — bundled, so no
    # runtime download. See NOTICE for attribution.
    _UDPIPE_MODEL_FILE = 'english-ewt.udpipe'

    def _udpipe_model_path(self):
        from importlib.resources import files
        try:
            return str(files('poetit').joinpath('data', self._UDPIPE_MODEL_FILE))
        except Exception:
            here = os.path.dirname(os.path.abspath(__file__))
            return os.path.join(here, 'data', self._UDPIPE_MODEL_FILE)

    def _ensure_udpipe_model(self):
        """Load the bundled UDPipe model once; thread-safe. Returns it or None."""
        with self._udpipe_lock:
            if self._udpipe_model is not None or self._udpipe_failed:
                return self._udpipe_model
        model = _UDModel.load(self._udpipe_model_path()) if UDPIPE_AVAILABLE else None
        with self._udpipe_lock:
            if model:
                self._udpipe_model = model
            else:
                self._udpipe_failed = True
            return self._udpipe_model

    @property
    def diagram_ready(self):
        with self._udpipe_lock:
            udpipe = self._udpipe_model is not None
        with self._stanza_lock:
            stanza = self._stanza_nlp is not None
        return udpipe or stanza

    @property
    def diagram_backend(self):
        """Which parser the diagram is currently using: 'stanza' (quality mode),
        'udpipe' (bundled default), or None if neither has loaded yet."""
        with self._stanza_lock:
            if self._stanza_nlp is not None:
                return 'stanza'
        with self._udpipe_lock:
            if self._udpipe_model is not None:
                return 'udpipe'
        return None

    @staticmethod
    def _segment_spans(text):
        """(start, end) char spans of sentences in text.

        Segmentation is delegated to NLTK's trained Punkt model, which breaks on
        real sentence boundaries (terminal punctuation, abbreviation-aware) and
        — unlike UDPipe's tokenizer — does NOT treat a capitalised word after a
        line break as a new sentence. That keeps a verse sentence spanning
        several lines intact, e.g. the lines of a sonnet up to its full stop.
        Offsets are recovered by locating each returned sentence in the source.
        """
        spans, pos = [], 0
        for sent in nltk.sent_tokenize(text):
            idx = text.find(sent, pos)
            if idx < 0:
                continue
            spans.append((idx, idx + len(sent)))
            pos = idx + len(sent)
        if not spans and text.strip():
            spans = [(0, len(text))]
        return spans

    def get_diagram_doc(self, text):
        """Dependency parse for the diagram, as a Stanza-shaped doc.

        Sentences are segmented with Punkt (_segment_spans). Each span is parsed
        by the best backend available: Stanza in 'quality mode' if it is
        installed and its ewt model is present, otherwise the bundled UDPipe
        model. Both feed the renderer the same _DiagramWord shape.
        """
        spans = self._segment_spans(text)
        if not spans:
            return _DiagramDoc([])
        stanza_pl = self._ensure_stanza_pipeline()
        udpipe_model = self._ensure_udpipe_model() if stanza_pl is None else None
        if stanza_pl is None and udpipe_model is None:
            return None
        sentences = []
        for start, end in spans:
            seg = " ".join(text[start:end].split())   # one normalized line
            if stanza_pl is not None:
                words = self._stanza_words(stanza_pl, seg)
            else:
                words = self._udpipe_words(udpipe_model, seg)
            if not words:
                continue
            sent = _DiagramSentence()
            sent.words = words
            sent.tokens = [_DiagramToken(start)]   # offset into the original text
            sent.text = seg
            sentences.append(sent)
        return _DiagramDoc(sentences)

    @staticmethod
    def _udpipe_words(model, seg):
        # 'presegmented' => the span is one sentence; UDPipe will not re-split it.
        tokenizer = model.newTokenizer("presegmented")
        if tokenizer is None:
            return None
        tokenizer.setText(seg)
        s = _UDSentence()
        if not tokenizer.nextSentence(s, _UDError()):
            return None
        model.tag(s, _UDModel.DEFAULT)
        model.parse(s, _UDModel.DEFAULT)
        out = []
        for uw in list(s.words)[1:]:   # words[0] is the artificial <root> token
            w = _DiagramWord()
            w.id, w.text, w.lemma = uw.id, uw.form, uw.lemma
            w.upos, w.xpos = uw.upostag, uw.xpostag
            w.head, w.deprel = uw.head, uw.deprel
            out.append(w)
        return out

    # ------------------------------------------------------------------ #
    # Meter analysis
    # ------------------------------------------------------------------ #

    def _is_function(self, word, pos_tag, prev_word=None, dep=None):
        if dep is not None:
            if dep in ('ROOT', 'root'):   # spaCy uppercase, Stanza/UD lowercase
                return False
            if dep in _WEAK_DEPS:
                return True
        if pos_tag in _FUNCTION_POS:
            return True
        if word.lower() in _WEAK_WORDS:
            return True
        if word.lower() in _AUXILIARIES:
            return True
        if (pos_tag in ('VBN', 'VBD') and prev_word
                and prev_word.lower() in _HAVE_AUX):
            return True
        return False

    def _syllabify_word(self, word, is_function=False):
        lower   = word.lower()
        entries = self._cmu.get(lower)

        if entries:
            best    = self._best_cmu_entry(lower)
            primary = [int(ph[-1]) for ph in best if ph[-1].isdigit()]
            if is_function and len(primary) == 1:
                stresses = None
                for entry in entries:
                    s = [int(ph[-1]) for ph in entry if ph[-1].isdigit()]
                    if s and max(s) == 0:
                        stresses = s
                        break
                if stresses is None:
                    stresses = [0]
            else:
                stresses = primary
        else:
            stresses = [0] * max(1, self._fallback_syllables(lower))

        n = max(1, len(stresses))
        wlen = len(word)
        base, rem = divmod(wlen, n)
        chunks, cursor = [], 0
        for k in range(n):
            size = base + (1 if k < rem else 0)
            chunks.append(word[cursor:cursor + size])
            cursor += size

        return [(chunks[k], stresses[k] if k < len(stresses) else 0) for k in range(n)]

    def _tag_line(self, text):
        word_tokens = re.findall(r'[A-Za-z]+', text)
        if not word_tokens:
            return []
        doc = self.get_stanza_doc(text)
        if doc is not None:
            stanza_words = [
                (w.text, w.xpos or 'NN', w.deprel or '')
                for sent in doc.sentences
                for w in sent.words
                if w.text.isalpha()
            ]
            # Only use Stanza tags when the alpha-token count matches what the
            # regex produces; contractions and MWT can cause a mismatch that
            # would misalign every subsequent tag in the line.
            if len(stanza_words) == len(word_tokens):
                return stanza_words
        try:
            tagged = nltk.pos_tag(word_tokens)
        except Exception:
            tagged = [(w, "NN") for w in word_tokens]
        return [(w, tag, '') for w, tag in tagged]

    def _compose_meter_line_nltk(self, text):
        tagged   = self._tag_line(text)
        tag_iter = iter(tagged)
        parts, prev_word = [], None
        for token in re.split(r'([A-Za-z]+)', text):
            if not token:
                continue
            if re.match(r'[A-Za-z]+$', token):
                _, pos_tag, dep = next(tag_iter, (token, "NN", ""))
                func_flag = self._is_function(token, pos_tag, prev_word, dep or None)
                sylls     = self._syllabify_word(token, func_flag)
                rendered  = []
                for stext, stress in sylls:
                    if stress == 1:   rendered.append(stext.upper())
                    elif stress == 2: rendered.append(stext.capitalize())
                    else:             rendered.append(stext.lower())
                parts.append(SEP_DOT.join(rendered))
                prev_word = token
            else:
                parts.append(token)
        return "".join(parts)

    def _compose_meter_line_prosodic(self, text):
        if not _PROSODIC_AVAILABLE or not text.strip():
            return None
        try:
            t = _prosodic.Text(text)
            t.parse()
            if not t.lines:
                return None
            line = t.lines[0]
            bp   = line.best_parse
            if bp is None:
                return None
            slots    = [s for s in bp.slots if s.syll is not None]
            slot_idx = 0
            parts    = []
            for wt in line.get_list('WordToken'):
                word_txt  = wt.txt
                word_core = word_txt.strip()
                leading   = word_txt[: len(word_txt) - len(word_core)]
                if leading:
                    parts.append(leading)
                if not word_core or not any(c.isalpha() for c in word_core):
                    parts.append(word_core)
                    continue
                target_len  = len(re.sub(r"[^a-z']+", '', word_core.lower()))
                accumulated = 0
                word_slots  = []
                while slot_idx < len(slots) and accumulated < target_len:
                    stxt        = slots[slot_idx].syll.txt
                    accumulated += len(re.sub(r"[^a-z']+", '', stxt.lower()))
                    word_slots.append(slots[slot_idx])
                    slot_idx += 1
                rendered = [
                    slot.syll.txt.upper() if slot.meter_val == 's' else slot.syll.txt.lower()
                    for slot in word_slots
                ]
                parts.append(SEP_DOT.join(rendered))
            result = "".join(parts)
            return result if result else None
        except Exception:
            return None

    def compose_meter_line(self, text):
        result = self._compose_meter_line_prosodic(text)
        if result is not None:
            return result
        return self._compose_meter_line_nltk(text)
