# Poetit

A desktop poetry editor with built-in syllable counting, meter analysis, rhyme detection, thesaurus, dictionary, spell check, dependency diagrams, and git-based version control. Built with Python and tkinter — no Electron, no browser. 

Python dependencies are ~1.7 GB installed (mostly PyTorch's CPU inference library, used by Stanza for parsing). Install torch from the CPU index as shown below — the default PyPI torch is a CUDA build that adds ~4.5 GB poetit can never use.

---

## Install

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU-only torch, ~4.5 GB smaller
pip install -e .
```

`pip install -e .` installs every dependency, including the ones behind the meter, diagram, and spell-check features. The dependency diagram additionally needs Stanza's English model, which is not bundled — download it once:

```bash
python -c "import stanza; stanza.download('en', package='ewt', processors='tokenize,mwt,pos,lemma,depparse')"
```

To reclaim another ~60 MB, strip the parts of stanza/torch that poetit never
executes (test suites, C++ headers, bundled binaries):

```bash
python3 scripts/trim_nlp_footprint.py --keep-pyi \
    --site-packages "$(python -c 'import site; print(site.getsitepackages()[0])')"
```

Each feature is powered by a specific package, all installed by default:

| Feature | Powered by |
|---|---|
| Enhanced meter analysis | `prosodic` (NLTK fallback otherwise) |
| Dependency diagram | `stanza`, `resvg_py`, `Pillow` |
| Spell check | `pyspellchecker` |
| Version control | `dulwich` |

NLTK data (punkt tokenizer, POS tagger) is downloaded automatically on first launch if not already present. CMUDict, WordNet, and the thesaurus are bundled with the package — no separate download needed.

---

## Run

```bash
poetit
```

or

```bash
python -m poetit
```

---

## Features

### Line-by-line editing

| Key | Action |
|---|---|
| Enter | Split line / create new line below |
| Backspace at position 0 | Merge line into the one above |
| Up / Down arrows | Move between lines |
| Tab | Move to next line |
| Ctrl+Z / Ctrl+Y | Undo / Redo |

### Syllable counts

A grey margin column to the right of each line shows its syllable count. Counts come from the bundled CMU Pronouncing Dictionary, with NLTK's SyllableTokenizer as a fallback for words not in the dictionary.

### Rhyme scheme

A column on the far right displays the rhyme scheme letter for each line (A, B, C …). Two lines share a letter when their final words share the same phoneme suffix from the last stressed vowel onward (CMUDict-based). Blank lines get no letter.

### Meter

Click **Meter** in the toolbar to replace each line in place with a stress-marked version of itself; click it again to restore the text. Stress is shown by letter case:

```
SHALL i com·PARE thee TO a SUM·mers DAY
```

- **UPPERCASE** — stressed
- **Capitalized** — secondary stress (NLTK fallback only)
- **lowercase** — unstressed
- **·** — syllable boundary

Function words (determiners, auxiliaries, prepositions, conjunctions, etc.) are automatically destressed. If the `prosodic` library is installed it is used for metrically-informed parsing, marking syllables as stressed or unstressed only; otherwise NLTK POS tagging with CMUDict stress values is used, which additionally distinguishes secondary stress.

### Rhyme lookup

Click anywhere on a word in a line, then click **Rhyme** to see a scrollable list of rhyming words. Click a word in the list to replace the word under the cursor. You can also type a word directly into the lookup field beside the Rhyme button and press Enter.

### Definition

Click on a word then click **Definition** to see its WordNet entries grouped by part of speech, with synonyms and usage examples. Bundled WordNet data — no download required.

### Thesaurus

Click on a word then click **Thesaurus** to see synonyms. Click a synonym to replace the word in your poem.

### Spell check

Click **Spell** to toggle inline spell-checking (powered by `pyspellchecker`). Misspelled words get a red underline; hover one to see suggestions and click a suggestion to apply it.

### Dependency diagram

Click in your poem then click **Diagram** to render a Stanza dependency parse of the sentence containing the cursor. (Sentences are segmented across the whole poem, so a diagram can span more than one line.) It shows the grammatical relationships between words, with POS tags and dependency labels. Stanza's English model downloads automatically on first use.

---

## Version control

Poetit uses git (via `dulwich`) to keep a history of every version of your poem. No git installation required — dulwich is a pure-Python git implementation, so version history works identically in the flatpak, snap, and on Windows.

### The repository folder

Poems live in a single git repository at `~/Documents/Poetit`. The first time an operation needs it (for example **Import** or **Export**), Poetit offers to create the folder and seed it with a demo poem.

### Repository operations

| Menu item | What it does |
|---|---|
| File → Browse Repository | Open the repository folder and browse its poems |
| File → Import… | Copy an external `.txt` file into the repository |
| File → Export… | Save the current poem to a path outside the repository |

### Making versions

Click **Make Version** in the toolbar to commit the current poem. A dialog prompts for a version message (pre-filled with the current timestamp). Each commit snapshots the poem file and its metadata.

### Version Tree

Click **Version Tree** to browse the commit history for the current poem. Click any version card to load it into the editor. If you have unsaved edits, a **Commit / Discard** dialog appears first:

- **Commit** — opens the Make Version dialog to save your current work before switching
- **Discard** — discards unsaved edits and loads the selected version

---

## File format

Each poem is saved as a plain UTF-8 `.txt` file. A sidecar `.txt.meta` JSON file stores font settings and per-character run metadata. The `.meta` file is committed to the repository alongside the poem.

---

## Menu reference

**File**

| Item | Action |
|---|---|
| New | Clear the editor (prompts to save if dirty) |
| Open… | Open a `.txt` file from anywhere on disk |
| Save | Save to the current path; if inside a repo, prompts for a filename |
| Save As… | Save to a new path |
| Browse Repository | Open the repository folder and browse its poems |
| Import… | Bring an external file into the repo |
| Export… | Write the poem to a file outside the repo |
| Exit | Quit (prompts to save if dirty) |

**Font / Size** — change the editor typeface and size. Font choice is persisted in the `.meta` file.

**Theme** — pick a light or dark theme, or create and edit your own from **Theme → Edit Themes…**. Your choice is remembered between sessions.

---

## Development

```bash
pip install -e ".[dev]"   # includes pytest
python -m pytest tests/ -v
```

Tests cover `file_io` (round-trip write/read, metadata, edge cases), `linguistics` (syllable counting, rhyme scheme, rhyme lookup, stress detection, word-at-cursor), the app layer, the git version-control layer, and a Stanza smoke test.

---

## Requirements

- Python ≥ 3.10
- nltk ≥ 3.8 *(syllables, POS tagging, WordNet)*
- prosodic ≥ 3.0 *(meter analysis)*
- stanza ≥ 1.7 *(dependency diagram; downloads its English model on first use)*
- resvg_py ≥ 0.3 *(diagram rendering)*
- Pillow ≥ 9.0 *(diagram display)*
- pyspellchecker ≥ 0.7 *(spell check)*
- dulwich ≥ 0.22 *(version control)*
