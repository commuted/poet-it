import tkinter as tk
import tkinter.font as tkfont
from nltk.corpus import wordnet as wn

try:
    import resvg_py as _resvg
    from PIL import Image as _PILImage, ImageTk as _PILImageTk
    import io as _io
    DIAGRAM_AVAILABLE = True
except ImportError:
    DIAGRAM_AVAILABLE = False

_POS_LABEL = {'n': 'Noun', 'v': 'Verb', 'a': 'Adjective', 's': 'Adjective', 'r': 'Adverb'}


def show_word_list_popup(root, title, header, words, on_select, width=220, height=320, note=None):
    popup = tk.Toplevel(root)
    popup.title(title)
    popup.transient(root)
    popup.resizable(False, True)

    if note:
        tk.Label(popup, text=note, anchor='w', fg='#226622').pack(fill=tk.X, padx=6, pady=(6, 0))

    tk.Label(popup, text=header, anchor='w').pack(fill=tk.X, padx=6, pady=(6, 2))

    if not words:
        tk.Label(popup, text='None found.', fg='gray').pack(padx=6, pady=6)
        tk.Button(popup, text='Close', command=popup.destroy).pack(pady=6)
        return

    tk.Label(popup, text=f'{len(words)} found — click a word (or press Enter) to insert.',
             anchor='w', fg='gray').pack(fill=tk.X, padx=6)

    outer = tk.Frame(popup)
    outer.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    # A single Listbox renders thousands of rows instantly. The previous design
    # created one Button (an X window) per word, which hung the UI and pegged
    # ibus on large lists — e.g. "saints" returns 3654 rhymes, "lost" 1645.
    sb = tk.Scrollbar(outer, orient='vertical')
    lb = tk.Listbox(outer, height=max(6, height // 18), width=max(16, width // 8),
                    activestyle='dotbox', bg='white', exportselection=False,
                    yscrollcommand=sb.set)
    sb.configure(command=lb.yview)
    lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.RIGHT, fill=tk.Y)

    lb.insert('end', *words)
    lb.selection_set(0)
    lb.activate(0)
    lb.focus_set()

    def _choose(_event=None):
        sel = lb.curselection()
        if not sel:
            return
        word = lb.get(sel[0])
        popup.destroy()
        on_select(word)

    def _scroll(event):
        if event.num == 4:   lb.yview_scroll(-1, 'units')
        elif event.num == 5: lb.yview_scroll(1, 'units')
        else:                lb.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    # Single click inserts, matching the old one-Button-per-word behaviour.
    # ButtonRelease fires after the press has updated the selection.
    lb.bind('<ButtonRelease-1>', _choose)
    lb.bind('<Return>', _choose)
    popup.bind('<Escape>', lambda e: popup.destroy())
    for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
        lb.bind(seq, _scroll)


def show_definition_popup(root, word):
    synsets = wn.synsets(word)
    popup = tk.Toplevel(root)
    popup.title(f'Definition: "{word}"')
    popup.transient(root)
    popup.resizable(True, True)

    outer = tk.Frame(popup)
    outer.pack(fill=tk.BOTH, expand=True)

    cv = tk.Canvas(outer, width=380, height=440, bg='white', highlightthickness=0)
    sb = tk.Scrollbar(outer, orient='vertical', command=cv.yview)
    cv.configure(yscrollcommand=sb.set)
    cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.RIGHT, fill=tk.Y)

    inner = tk.Frame(cv, bg='white', padx=10, pady=6)
    cv_win = cv.create_window((0, 0), window=inner, anchor='nw')

    cv.bind('<Configure>', lambda e: cv.itemconfig(cv_win, width=e.width))

    def _scroll(event):
        if event.num == 4:   cv.yview_scroll(-1, 'units')
        elif event.num == 5: cv.yview_scroll(1, 'units')
        else:                cv.yview_scroll(int(-1 * (event.delta / 120)), 'units')
    for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
        cv.bind(seq, _scroll)
        inner.bind(seq, _scroll)

    f_word = tkfont.Font(family='Helvetica', size=13, weight='bold')
    f_pos  = tkfont.Font(family='Helvetica', size=10, weight='bold', slant='italic')
    f_def  = tkfont.Font(family='Helvetica', size=10)
    f_sub  = tkfont.Font(family='Helvetica', size=9)

    tk.Label(inner, text=word.lower(), font=f_word, bg='white',
             anchor='w').pack(fill=tk.X, pady=(0, 6))

    if not synsets:
        tk.Label(inner, text='No definitions found.', font=f_def,
                 fg='gray', bg='white', anchor='w').pack(fill=tk.X)
    else:
        by_pos = {}
        for s in synsets:
            by_pos.setdefault(s.pos(), []).append(s)
        for pos in [p for p in ('n', 'v', 'a', 's', 'r') if p in by_pos]:
            tk.Label(inner, text=_POS_LABEL.get(pos, pos), font=f_pos,
                     fg='#555', bg='white', anchor='w').pack(fill=tk.X, pady=(8, 2))
            for idx, s in enumerate(by_pos[pos], 1):
                tk.Label(inner, text=f'{idx}.  {s.definition()}', font=f_def,
                         bg='white', anchor='w', justify='left',
                         wraplength=340).pack(fill=tk.X, padx=(8, 0))
                lemmas = [n.replace('_', ' ') for n in s.lemma_names()
                          if n.lower() != word.lower()]
                if lemmas:
                    tk.Label(inner, text='syn: ' + ',  '.join(lemmas), font=f_sub,
                             fg='#336', bg='white', anchor='w', justify='left',
                             wraplength=340).pack(fill=tk.X, padx=(20, 0))
                for ex in s.examples():
                    tk.Label(inner, text=f'"{ex}"', font=f_sub, fg='#555',
                             bg='white', anchor='w', justify='left',
                             wraplength=340).pack(fill=tk.X, padx=(20, 0))
                tk.Frame(inner, height=4, bg='white').pack()

    inner.update_idletasks()
    cv.configure(scrollregion=cv.bbox('all'))
    tk.Button(popup, text='Close', command=popup.destroy).pack(pady=6)


def _svg_escape(text):
    return (text.replace('&', '&amp;').replace('<', '&lt;')
                .replace('>', '&gt;').replace('"', '&quot;'))


# --- Dependency-diagram arc geometry -------------------------------------- #
# Arcs are flat-topped brackets: a vertical riser, a rounded corner, a level
# horizontal apex, a rounded corner, and a vertical drop. Distinct apex heights
# per nesting level + risers anchored at word x-positions make the arcs
# non-crossing by construction. Tune these to taste; ARC_SCALE scales the whole
# diagram uniformly.
ARC_SCALE      = 1.0   # uniform multiplier for every dimension below
ARC_RISE       = 14    # straight vertical riser before the corner (px)
ARC_APEX       = 18    # flat-top height above the attachment line, level 1 (px)
ARC_CORNER     = 25 #8     # corner radius / distance to horizontal on the X axis (px)
ARC_LEVEL_STEP = 28 #34    # extra apex height per nesting level (px)
ARC_COL_W      = 110   # horizontal pixels per word


def _arc_levels(words):
    """Assign each dependent word a nesting level (1-based) via interval graph coloring."""
    spans = [
        (min(w.id, w.head), max(w.id, w.head), w.id)
        for w in words if w.head > 0
    ]
    spans.sort(key=lambda s: (s[1] - s[0], s[0]))
    levels, buckets = {}, []
    for lo, hi, wid in spans:
        placed = False
        for lvl_idx, bucket in enumerate(buckets):
            if not any(lo < bhi and hi > blo for blo, bhi in bucket):
                bucket.append((lo, hi))
                levels[wid] = lvl_idx + 1
                placed = True
                break
        if not placed:
            buckets.append([(lo, hi)])
            levels[wid] = len(buckets)
    return levels


def _stanza_to_svg(doc, bg="#fffef0", color="#003388", sent_index=0):
    """Render one sentence of a Stanza doc as a dependency arc diagram SVG."""
    if not doc or not doc.sentences:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="300" height="60"'
                f' style="background:{bg}"><text x="10" y="35"'
                f' font-family="sans-serif" font-size="13" fill="#555">'
                f'No parse available.</text></svg>')

    words = doc.sentences[sent_index].words
    n = len(words)

    sc           = ARC_SCALE
    col_w        = ARC_COL_W * sc       # horizontal pixels per word
    pad_x        = 60 * sc              # left/right margin
    entry_offset = 22 * sc              # gap between word baseline and arc attachment
    level_step   = ARC_LEVEL_STEP * sc  # extra apex height per nesting level
    rise         = ARC_RISE * sc        # straight vertical riser
    corner       = ARC_CORNER * sc      # corner radius / x distance to horizontal
    # Level-1 flat-top height. Floor it at riser + a full-radius corner, or the
    # corner gets squashed and stops responding to the radius at the lowest level.
    apex         = max(ARC_APEX * sc, rise + corner)
    pad_top      = 28 * sc              # clearance above topmost arc label
    root_clear   = 42 * sc              # space needed for the ROOT indicator
    fs_word      = round(13 * sc)       # word font size
    fs_tag       = round(10 * sc)       # POS tag / label font size
    stroke       = 1.5 * sc

    arc_lvls  = _arc_levels(words)
    max_level = max(arc_lvls.values(), default=1)

    top_apex = apex + (max_level - 1) * level_step
    entry_y  = pad_top + max(top_apex + 14 * sc, root_clear)
    baseline = entry_y + entry_offset
    total_h  = baseline + 48 * sc
    total_w  = pad_x * 2 + max(n - 1, 0) * col_w

    arcs, arc_labels, word_els = [], [], []

    marker = (
        f'<defs><marker id="arr" markerWidth="7" markerHeight="7"'
        f' refX="6" refY="3.5" orient="auto" markerUnits="userSpaceOnUse">'
        f'<path d="M 0 0 L 7 3.5 L 0 7 Z" fill="{color}"/>'
        f'</marker></defs>'
    )

    for word in words:
        xi = pad_x + (word.id - 1) * col_w

        word_els.append(
            f'<text x="{xi:.1f}" y="{baseline:.1f}" text-anchor="middle"'
            f' font-family="Helvetica,Arial,sans-serif" font-size="{fs_word}"'
            f' font-weight="bold" fill="#111">{_svg_escape(word.text)}</text>'
        )
        pos = word.xpos or word.upos or ''
        word_els.append(
            f'<text x="{xi:.1f}" y="{baseline + 18 * sc:.1f}" text-anchor="middle"'
            f' font-family="Helvetica,Arial,sans-serif" font-size="{fs_tag}"'
            f' fill="#666">{_svg_escape(pos)}</text>'
        )

        if word.head == 0:
            root_y0  = entry_y - 30 * sc
            lbl_base = root_y0 - 5 * sc
            arcs.append(
                f'<line x1="{xi:.1f}" y1="{root_y0:.1f}" x2="{xi:.1f}" y2="{entry_y:.1f}"'
                f' stroke="{color}" stroke-width="{stroke:.2f}" marker-end="url(#arr)"/>'
            )
            # White rect behind the label, like the deprel labels — the root
            # word is the head of its dependents, so their risers run vertically
            # at this x and would otherwise bisect the "root" text.
            lbl_w = len("root") * 6 * sc + 6 * sc
            arc_labels.append(
                f'<rect x="{xi - lbl_w / 2:.1f}" y="{lbl_base - 10 * sc:.1f}"'
                f' width="{lbl_w:.1f}" height="{11 * sc:.1f}" fill="{bg}"/>'
            )
            arc_labels.append(
                f'<text x="{xi:.1f}" y="{lbl_base:.1f}" text-anchor="middle"'
                f' font-family="Helvetica,Arial,sans-serif" font-size="{fs_tag}"'
                f' fill="{color}">root</text>'
            )
        else:
            xh    = pad_x + (word.head - 1) * col_w
            level = arc_lvls.get(word.id, 1)
            top   = entry_y - (apex + (level - 1) * level_step)   # flat-top y
            mid_x = (xi + xh) / 2
            sgn   = 1 if xi > xh else -1
            cdx   = corner                                        # corner x extent
            cdy   = corner                                        # corner y extent (full radius at every level)

            # Flat-topped bracket: riser, rounded corner, horizontal apex,
            # rounded corner, drop. Distinct apex heights per level + verticals
            # anchored at the word x-positions keep arcs from crossing.
            arcs.append(
                f'<path d="M {xh:.1f},{entry_y:.1f}'
                f' L {xh:.1f},{top + cdy:.1f}'
                f' Q {xh:.1f},{top:.1f} {xh + sgn * cdx:.1f},{top:.1f}'
                f' L {xi - sgn * cdx:.1f},{top:.1f}'
                f' Q {xi:.1f},{top:.1f} {xi:.1f},{top + cdy:.1f}'
                f' L {xi:.1f},{entry_y:.1f}"'
                f' stroke="{color}" fill="none" stroke-width="{stroke:.2f}"'
                f' marker-end="url(#arr)"/>'
            )

            # Label centered on the horizontal apex.
            lbl_text = word.deprel or ""
            lbl_w = len(lbl_text) * 6 * sc + 6 * sc
            arc_labels.append(
                f'<rect x="{mid_x - lbl_w / 2:.1f}" y="{top - 6 * sc:.1f}"'
                f' width="{lbl_w:.1f}" height="{11 * sc:.1f}" fill="{bg}"/>'
            )
            arc_labels.append(
                f'<text x="{mid_x:.1f}" y="{top + 4 * sc:.1f}" text-anchor="middle"'
                f' font-family="Helvetica,Arial,sans-serif" font-size="{fs_tag}"'
                f' fill="{color}">{_svg_escape(lbl_text)}</text>'
            )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg"'
        f' width="{total_w}" height="{total_h}" style="background:{bg}">\n'
        + marker + '\n'
        + '\n'.join(arcs) + '\n'
        + '\n'.join(arc_labels) + '\n'
        + '\n'.join(word_els) + '\n'
        + '</svg>'
    )


def show_diagram_popup(root, text, doc, screen_w, screen_h, sent_index=0):
    svg = _stanza_to_svg(doc, sent_index=sent_index)
    png_bytes = _resvg.svg_to_bytes(svg_string=svg)
    img = _PILImage.open(_io.BytesIO(png_bytes))

    popup = tk.Toplevel(root)
    popup.title("Dependency Diagram")
    popup.transient(root)
    popup.resizable(True, True)

    tk.Label(popup, text=text, font=("Helvetica", 11), wraplength=700,
             justify="left", pady=4).pack(fill=tk.X, padx=8)

    # Word annotation row: text / deprel / upos
    info_frame = tk.Frame(popup, bg="#eef2fb")
    info_frame.pack(fill=tk.X, padx=8, pady=(0, 4))
    if doc and doc.sentences:
        for word in doc.sentences[sent_index].words:
            if word.text.isalpha():
                cell = tk.Frame(info_frame, bg="#eef2fb", padx=4)
                cell.pack(side="left")
                tk.Label(cell, text=word.text,   font=("Courier", 9, "bold"), bg="#eef2fb").pack()
                tk.Label(cell, text=word.deprel, font=("Courier", 8), fg="#005500", bg="#eef2fb").pack()
                tk.Label(cell, text=word.upos,   font=("Courier", 8), fg="#550000", bg="#eef2fb").pack()

    frame = tk.Frame(popup)
    frame.pack(fill=tk.BOTH, expand=True)

    h_sb = tk.Scrollbar(frame, orient="horizontal")
    v_sb = tk.Scrollbar(frame, orient="vertical")
    cv   = tk.Canvas(frame, bg="white", xscrollcommand=h_sb.set, yscrollcommand=v_sb.set)
    h_sb.configure(command=cv.xview)
    v_sb.configure(command=cv.yview)
    h_sb.pack(side=tk.BOTTOM, fill=tk.X)
    v_sb.pack(side=tk.RIGHT,  fill=tk.Y)
    cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    photo = _PILImageTk.PhotoImage(img)
    cv.create_image(4, 4, anchor="nw", image=photo)
    cv._img_ref = photo
    cv.configure(scrollregion=(0, 0, img.width + 8, img.height + 8))

    for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        cv.bind(seq, lambda e, s=cv: (
            s.yview_scroll(-1, "units") if e.num == 4
            else s.yview_scroll(1, "units") if e.num == 5
            else s.xview_scroll(int(-1 * (e.delta / 120)), "units")
        ))

    w = min(img.width + 30, screen_w - 100)
    h = min(img.height + 140, screen_h - 100)
    popup.geometry(f"{w}x{h}")
    tk.Button(popup, text="Close", command=popup.destroy).pack(pady=6)
