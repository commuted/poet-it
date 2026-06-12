# Poetit

A desktop poetry editor with built-in syllable counting, meter analysis, rhyme detection, thesaurus, dictionary, dependency diagrams, and git-based version control. Built with Python and tkinter — no Electron, no browser. 

Python dependencies are ~1.7 GB installed (mostly PyTorch's CPU inference library, used by Stanza for parsing). Install torch from the CPU index as shown below — the default PyPI torch is a CUDA build that adds ~4.5 GB poetit can never use.

---

## Install

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU-only torch, ~4.5 GB smaller
pip install -e .
```

For the full feature set install the optional extras:

```bash
pip install stanza resvg_py Pillow
python -c "import stanza; stanza.download('en', processors='tokenize,mwt,pos,lemma,depparse')"
```

To reclaim another ~60 MB, strip the parts of stanza/torch that poetit never
executes (test suites, C++ headers, bundled binaries):

```bash
python3 scripts/trim_nlp_footprint.py --keep-pyi \
    --site-packages "$(python -c 'import site; print(site.getsitepackages()[0])')"
```

| Feature | Requires |
|---|---|
| Meter analysis (enhanced) | `prosodic` |
| Dependency diagram | `stanza`, `resvg_py`, `Pillow` |
| Version control | `git` on PATH |

NLTK data (punkt tokenizer, POS tagger) is downloaded automatically on first launch if not already present. CMUDict and WordNet are bundled with the package — no separate download needed.

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

Each line of the poem is its own row. The editor behaves like a structured notepad rather than a free-form text area.

| Key | Action |
|---|---|
| Enter | Split line / create new line below |
| Backspace at position 0 | Merge line upward and delete row |
| Up / Down arrows | Move between lines |
| Tab | Move to next line |
| Ctrl+Z / Ctrl+Y | Undo / Redo |

Multi-line paste is supported — pasted text is split on newlines and distributed into rows automatically.

### Syllable counts

A grey margin column to the right of each line shows its syllable count. Counts come from the bundled CMU Pronouncing Dictionary, with NLTK's SyllableTokenizer as a fallback for words not in the dictionary.

### Rhyme scheme

A column on the far right displays the rhyme scheme letter for each line (A, B, C …). Two lines share a letter when their final words share the same phoneme suffix from the last stressed vowel onward (CMUDict-based). Blank lines get no letter.

### Meter

Click **Meter** in the toolbar to toggle a stress-marked display above each line. Stress is shown by letter case:

```
SHALL i com·PARE thee TO a SUM·mers DAY
```

- **UPPERCASE** — primary stress
- **Capitalized** — secondary stress
- **lowercase** — unstressed
- **·** — syllable boundary

Function words (determiners, auxiliaries, prepositions, conjunctions, etc.) are automatically destressed. If the `prosodic` library is installed it is used for metrically-informed parsing; otherwise NLTK POS tagging with CMUDict stress values is used.

### Rhyme lookup

Click anywhere on a word in a line, then click **Rhyme** to see a scrollable list of rhyming words. Click a word in the list to replace the word under the cursor. You can also type a word directly into the lookup field beside the Rhyme button and press Enter.

### Definition

Click on a word then click **Definition** to see its WordNet entries grouped by part of speech, with synonyms and usage examples. Bundled WordNet data — no download required.

### Thesaurus

Click on a word then click **Thesaurus** to see synonyms. Click a synonym to replace the word in your poem.

### Dependency diagram

Click on a line then click **Diagram** to render a Stanza dependency parse of that line. Shows the grammatical relationships between words, with POS tags and dependency labels. Requires `stanza`, `resvg_py`, and `Pillow`.

---

## Version control

Poetit uses git to keep a history of every version of your poem. It calls the `git` command-line tool, so git must be installed and on PATH.

### First launch

On first launch, Poetit offers to create a poetry repository folder (default: `~/Documents/poetry`). You can skip this and set it up later via **File → New Repository**.

### Repository operations

| Menu item | What it does |
|---|---|
| File → Open Repository | Open an existing git repository and browse its poems |
| File → New Repository | Create a new git repository and optionally migrate the current poem into it |
| File → Import… | Copy an external `.txt` file into the open repository |
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
| Open Repository | Open an existing git repo |
| New Repository | Create a new git repo |
| Import… | Bring an external file into the repo |
| Export… | Write the poem to a file outside the repo |
| Exit | Quit (prompts to save if dirty) |

**Font / Size** — change the editor typeface and size. Font choice is persisted in the `.meta` file.

---

## Development

```bash
pip install -e ".[dev]"   # includes pytest
python -m pytest tests/ -v
```

Tests cover `file_io` (round-trip write/read, metadata, edge cases) and `linguistics` (syllable counting, rhyme scheme, rhyme lookup, stress detection, word-at-cursor).

---

## Requirements

- Python ≥ 3.10
- nltk ≥ 3.8
- prosodic ≥ 3.0
- stanza ≥ 1.0 *(optional — diagram feature)*
- transformers>=4.0 *(optional — diagram feature)*
- resvg_py ≥ 0.3 *(optional — diagram rendering)*
- Pillow ≥ 9.0 *(optional — diagram display)*
- dulwich ≥ 0.22 *(version control)*
