"""Tables and dense data for reflowable Kindle text. No third-party imports.

The rules behind this module are in SKILL.md ("Tables and dense data").
In short: text reflows when the reader changes the font size and images do not,
so most data goes into reflowable shapes. Pick the form with plan(), then emit
HTML with prose_html(), ranked_list_html(), text_table_html(), or
record_cards_html(). render() does both steps.

Ladder, simplest first:
  prose         at most 3 numbers in total: write a sentence.
  ranked-list   one value per item: an ordered list, sorted by the claim.
  text-table    a label plus at most 2 short value columns that still fit one
                line at MIN_SCALE times the default font size.
  record-cards  everything else: one stacked label/value block per item.
  (image)       never chosen here. Use a kindle_charts / eink_style chart when the
                pattern is the point, and pair it with one of the forms above.

Widths are estimates in em from average glyph widths, not measured from the
reader's font. A Paperwhite page at the default size holds about LINE_EM em per
line. That is an assumption from the 9.5 pt preview page, not a device reading.
"""
import html
import re

_FIXED = re.compile(r"(?:^|[;\s])(?:min-|max-)?width\s*:\s*[\d.]+\s*(?:px|pt|in|cm|mm)\b")

LINE_EM = 26.0        # usable line at the default size: 3.62 in of text at 9.5 pt is about 27 em
MIN_SCALE = 2.0       # a text table must still fit on one line at 2x the default font size
MAX_TABLE_COLS = 3    # label + 2 values. Kindle's table viewer (pan and zoom) starts above 3
MAX_TABLE_ROWS = 12   # longer tables split into parts with a repeated header
MAX_LABEL_CHARS = 24  # longer row labels belong in record cards
MAX_VALUE_CHARS = 10  # a value cell is a number with its sign, not a phrase
MAX_HEADER_CHARS = 14
PAD_EM = 0.8          # left + right cell padding in the CSS below

TABLE_CSS = """
.kt-t { font-weight: bold; margin: 1em 0 0.3em 0; page-break-after: avoid; }
table.kt { width: 100%; border-collapse: collapse; margin: 0 0 0.4em 0; border-top: 2px solid #000; border-bottom: 2px solid #000; }
table.kt td, table.kt th { hyphens: none; }
table.kt th, table.kt td { padding: 0.2em 0.4em; vertical-align: top; text-align: left; line-height: 1.3; }
table.kt th { font-weight: bold; border-bottom: 2px solid #000; }
table.kt th.kt-n, table.kt td.kt-n { text-align: right; white-space: nowrap; }
table.kt tr { page-break-inside: avoid; }
table.kt tr.kt-f td { font-weight: bold; }
table.kt-c2 .kt-l { width: 60%; }
table.kt-c3 .kt-l { width: 46%; }
table.kt-c2 .kt-n { width: 40%; }
table.kt-c3 .kt-n { width: 27%; }
.kt-note { font-size: 0.85em; margin: 0 0 0.25em 0; }
ol.kt-rank li.kt-f { font-weight: bold; }
.kt-cards p, ol.kt-rank li, .kt-note { text-align: left; }
.rec.kt-f { border-left: 6px solid #000; }
.rec.kt-f .rec-h { font-size: 1.05em; }
"""

_W = {}
for ch in "0123456789": _W[ch] = 0.556
for ch in ",.:;'|!": _W[ch] = 0.28
for ch in "()[]": _W[ch] = 0.34
for ch in "+-=<>": _W[ch] = 0.584
_W[" "] = 0.26; _W["%"] = 0.85; _W["$"] = 0.556; _W["\u00a0"] = 0.26


def text_em(s, bold=False):
    """Estimated width of s in em. Uppercase 0.68, lowercase 0.5, digits 0.556."""
    w = 0.0
    for ch in str(s):
        if ch in _W: w += _W[ch]
        elif ch.isupper(): w += 0.68
        elif ch.islower(): w += 0.5
        else: w += 0.6
    return w * (1.07 if bold else 1.0)


def _word_em(s, bold=False):
    words = str(s).split()
    return max([text_em(w, bold) for w in words] or [0.0])


def _fmt(v):
    if isinstance(v, float): return "{:,.1f}".format(v).rstrip("0").rstrip(".")
    if isinstance(v, int) and not isinstance(v, bool): return "{:,}".format(v)
    return str(v)


def _sort(rows, sort_by, descending):
    if sort_by is None: return list(rows)
    def key(r):
        v = r[sort_by]
        return (0, v) if isinstance(v, (int, float)) else (1, str(v))
    return sorted(rows, key=key, reverse=descending)


def _focal(rows, label_col, focal):
    if focal is None: return set()
    want = {focal} if isinstance(focal, str) else set(focal)
    labels = {str(r[label_col]) for r in rows}
    missing = want - labels
    if missing: raise ValueError("focal row %s is not a row label" % sorted(missing))
    return want


def table_fit(columns, rows, numeric=None, line_em=LINE_EM):
    """Estimate the font scale at which a text table stops fitting one line per row.

    Label text may wrap at spaces, so only its longest word counts. Numeric cells
    never wrap (nowrap in TABLE_CSS). Returns dict(min_row_em, max_scale).
    """
    numeric = set(numeric if numeric is not None else _guess_numeric(columns, rows))
    total = 0.0
    for c in columns:
        cells = [_fmt(r[c]) for r in rows]
        if c in numeric:
            w = max([text_em(x, True) for x in cells] + [_word_em(c, True)])
        else:
            w = max([_word_em(x, True) for x in cells] + [_word_em(c, True)])
        total += w + PAD_EM
    return dict(min_row_em=round(total, 2), max_scale=round(line_em / total, 2) if total else 99.0)


def _guess_numeric(columns, rows):
    out = []
    for c in columns[1:]:
        vals = [r[c] for r in rows]
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals): out.append(c)
        elif all(isinstance(v, str) and v.strip() and v.strip()[0] in "+-$0123456789." for v in vals): out.append(c)
    return out


def plan(columns, rows, show=None, numeric=None, min_scale=MIN_SCALE):
    """Choose a reflowable form for rows (list of dicts) and say why.

    columns: column names, label column first. show: the columns the claim needs
    (label first). Columns left out of show become record-card detail lines.
    Returns dict(form, reasons, show, details, fit).
    """
    show = list(show or columns)
    if show[0] != columns[0]: raise ValueError("show must start with the label column %r" % columns[0])
    unknown = [c for c in show if c not in columns]
    if unknown: raise ValueError("unknown columns %s" % unknown)
    details = [c for c in columns if c not in show]
    values = len(show) - 1
    reasons = []
    if not rows: raise ValueError("no rows")
    if len(rows) * values <= 3 and not details:
        return dict(form="prose", reasons=["%d numbers in total read best as a sentence" % (len(rows) * values)],
                    show=show, details=details, fit=None)
    if values == 1 and not details:
        return dict(form="ranked-list", reasons=["one value per item: a ranked list reflows at any size"],
                    show=show, details=details, fit=None)
    fit = table_fit(show, rows, numeric)
    long_label = max(len(_fmt(r[show[0]])) for r in rows) > MAX_LABEL_CHARS
    long_value = any(len(_fmt(r[c])) > MAX_VALUE_CHARS for r in rows for c in show[1:])
    long_head = any(len(c) > MAX_HEADER_CHARS for c in show)
    if len(show) > MAX_TABLE_COLS: reasons.append("%d columns is over the cap of %d" % (len(show), MAX_TABLE_COLS))
    if fit["max_scale"] < min_scale: reasons.append("fits one line only up to %.1fx font size, under %.1fx" % (fit["max_scale"], min_scale))
    if long_label: reasons.append("a row label is over %d characters" % MAX_LABEL_CHARS)
    if long_value: reasons.append("a value cell is over %d characters" % MAX_VALUE_CHARS)
    if long_head: reasons.append("a header is over %d characters; abbreviate and add a key line" % MAX_HEADER_CHARS)
    if reasons:
        return dict(form="record-cards", reasons=reasons, show=show, details=details, fit=fit)
    reasons.append("%d columns, fits one line up to %.1fx font size" % (len(show), fit["max_scale"]))
    if details: reasons.append("%d more fields go in record cards below the table" % len(details))
    return dict(form="text-table", reasons=reasons, show=show, details=details, fit=fit)


def _notes_html(notes):
    return "".join('<p class="kt-note">%s</p>' % html.escape(n) for n in (notes or []))


def prose_html(sentence, notes=None):
    return "<p>%s</p>%s" % (html.escape(sentence), _notes_html(notes))


def ranked_list_html(rows, label, value, title=None, focal=None, sort_by=None, descending=True, fmt=None,
                     unit="", extra=None, notes=None):
    """Ordered list: '1. East: 1,702 (+9.1%)'. sort_by defaults to value. extra: column shown in parentheses."""
    fmt = fmt or _fmt
    hi = _focal(rows, label, focal)
    rows = _sort(rows, value if sort_by is None else sort_by, descending)
    items = []
    for r in rows:
        txt = "%s: %s%s" % (_fmt(r[label]), fmt(r[value]), (" " + unit) if unit else "")
        if extra: txt += " (%s)" % _fmt(r[extra])
        cls = ' class="kt-f"' if str(r[label]) in hi else ""
        items.append("<li%s>%s</li>" % (cls, html.escape(txt).replace(": ", ":\u00a0", 1)))
    head = '<p class="kt-t">%s</p>' % html.escape(title) if title else ""
    return '%s<ol class="kt-rank">%s</ol>%s' % (head, "".join(items), _notes_html(notes))


def text_table_html(columns, rows, title=None, focal=None, sort_by=None, descending=True, numeric=None,
                    notes=None, max_rows=MAX_TABLE_ROWS, min_scale=MIN_SCALE, fmt=None):
    """Small reflowable HTML table, class "kt". columns: label first, then at most 2 values.

    Raises ValueError when the table breaks a cap; use record_cards_html() instead.
    Longer tables split into parts of max_rows with the header repeated.
    Put units in the header ("Q3, k") and abbreviations or footnotes in notes.
    """
    fmt = fmt or {}
    if len(columns) > MAX_TABLE_COLS:
        raise ValueError("text tables take at most %d columns (label + 2); use record_cards_html()" % MAX_TABLE_COLS)
    if len(columns) < 2: raise ValueError("a table needs a label column and at least one value column")
    numeric = list(numeric if numeric is not None else _guess_numeric(columns, rows))
    shown = [{c: (fmt[c](r[c]) if c in fmt else _fmt(r[c])) for c in columns} for r in rows]
    for c in columns:
        if len(c) > MAX_HEADER_CHARS: raise ValueError("header %r is over %d characters; abbreviate and explain it in notes" % (c, MAX_HEADER_CHARS))
    for r in shown:
        if len(r[columns[0]]) > MAX_LABEL_CHARS: raise ValueError("row label %r is over %d characters; use record cards" % (r[columns[0]], MAX_LABEL_CHARS))
        for c in columns[1:]:
            if len(r[c]) > MAX_VALUE_CHARS: raise ValueError("cell %r is over %d characters; move words to notes" % (r[c], MAX_VALUE_CHARS))
    fit = table_fit(columns, shown, numeric)
    if fit["max_scale"] < min_scale:
        raise ValueError("table fits one line only up to %.1fx font size (need %.1fx); drop a column or use record cards" % (fit["max_scale"], min_scale))
    hi = _focal(rows, columns[0], focal)
    order = _sort(list(range(len(rows))), None, False)
    if sort_by is not None:
        order = sorted(order, key=lambda i: (0, rows[i][sort_by]) if isinstance(rows[i][sort_by], (int, float)) else (1, str(rows[i][sort_by])), reverse=descending)
    def cls(c): return "kt-n" if c in numeric else "kt-l"
    head = "<thead><tr>%s</tr></thead>" % "".join('<th class="%s" scope="col">%s</th>' % (cls(c), html.escape(c)) for c in columns)
    parts = [order[i:i + max_rows] for i in range(0, len(order), max_rows)]
    out = ""
    for p, idx in enumerate(parts):
        t = title if p == 0 or not title else "%s (continued, %d of %d)" % (title, p + 1, len(parts))
        if title: out += '<p class="kt-t">%s</p>' % html.escape(t)
        body = ""
        for i in idx:
            r = shown[i]; f = str(rows[i][columns[0]]) in hi
            body += "<tr%s>%s</tr>" % (' class="kt-f"' if f else "", "".join(
                '<td class="%s">%s</td>' % (cls(c), html.escape(r[c])) for c in columns))
        out += '<table class="kt kt-c%d">%s<tbody>%s</tbody></table>' % (len(columns), head, body)
    return out + _notes_html(notes)


def _split_unit(col):
    """'Q3, k' -> ('Q3', 'k'). A header without ', ' has no unit."""
    name, sep, unit = col.rpartition(", ")
    return (name, unit) if sep and name else (col, "")


def _pair(col, value):
    name, unit = _split_unit(col)
    v = html.escape(value)
    if len(value) <= MAX_VALUE_CHARS: v = v.replace(" ", "\u00a0")
    return "%s:\u00a0%s%s" % (html.escape(name), v, ("\u00a0" + html.escape(unit)) if unit else "")


def record_cards_html(columns, rows, title=None, focal=None, sort_by=None, descending=True, head_value=None,
                      notes=None, fmt=None):
    """One stacked block per row. The head line carries the label and the key value;
    the other fields run as 'Label: value unit' pairs joined by middots. Pairs never
    split across lines and the middot stays at the end of a line, so the block
    reflows at any font size. Empty fields are left out."""
    fmt = fmt or {}
    hi = _focal(rows, columns[0], focal)
    rows = _sort(rows, sort_by, descending)
    def val(r, c): return fmt[c](r[c]) if c in fmt else _fmt(r[c])
    out = '<p class="kt-t">%s</p>' % html.escape(title) if title else ""
    out += '<div class="kt-cards">'
    for r in rows:
        f = str(r[columns[0]]) in hi
        h = html.escape(val(r, columns[0]))
        if head_value: h += " \u00b7 " + _pair(head_value, val(r, head_value))
        pairs = [_pair(c, val(r, c)) for c in columns[1:]
                 if c != head_value and val(r, c) not in ("", "-", "\u2014")]
        out += '<div class="rec%s"><p class="rec-h">%s</p>%s</div>' % (
            " kt-f" if f else "", h, "<p>%s</p>" % "\u00a0\u00b7 ".join(pairs) if pairs else "")
    return out + "</div>" + _notes_html(notes)


def render(columns, rows, show=None, title=None, focal=None, sort_by=None, descending=True, notes=None,
           detail_title=None, sentence=None, numeric=None):
    """plan() then emit HTML. Returns (html, plan_dict). sentence is required for the prose form."""
    p = plan(columns, rows, show=show, numeric=numeric)
    form, show = p["form"], p["show"]
    if form == "prose":
        if not sentence: raise ValueError("prose form: pass sentence= with the numbers written out")
        return prose_html(sentence, notes), p
    if form == "ranked-list":
        return ranked_list_html(rows, show[0], show[1], title=title, focal=focal, sort_by=sort_by,
                                descending=descending, notes=notes), p
    if form == "text-table":
        # Notes (the abbreviation key) sit right under the table, where the short headers appear.
        out = text_table_html(show, rows, title=title, focal=focal, sort_by=sort_by, descending=descending,
                              numeric=numeric, notes=notes)
        if p["details"]:
            out += record_cards_html([show[0]] + p["details"], rows, title=detail_title or "Other fields",
                                     focal=focal, sort_by=sort_by, descending=descending)
        return out, p
    head = show[1] if len(show) > 1 else None
    return record_cards_html(columns, rows, title=title, focal=focal, sort_by=sort_by, descending=descending,
                             head_value=head, notes=notes), p


def lint_table_html(markup):
    """Problems with <table> elements in one XHTML document string (empty list = OK).

    Flags more than MAX_TABLE_COLS columns, nested tables, and fixed px/pt widths.
    Uses lxml when present; the caller decides whether a skip is acceptable.
    """
    from lxml import etree
    root = etree.fromstring(markup.encode("utf-8"))
    probs = []
    tables = root.xpath("//*[local-name()='table']")
    for n, t in enumerate(tables, start=1):
        if t.xpath(".//*[local-name()='table']"): probs.append("table %d is nested" % n)
        cols = 0
        for tr in t.xpath(".//*[local-name()='tr']"):
            k = 0
            for cell in tr.xpath("./*[local-name()='td' or local-name()='th']"):
                try: k += int(cell.get("colspan", "1"))
                except ValueError: k += 1
            cols = max(cols, k)
        if cols > MAX_TABLE_COLS:
            probs.append("table %d has %d columns (max %d); use record cards" % (n, cols, MAX_TABLE_COLS))
        for el in [t] + t.xpath(".//*"):
            st = (el.get("style") or "") + " " + (el.get("width") or "")
            if _FIXED.search(st) or (el.get("width") or "").strip().isdigit():
                probs.append("table %d uses a fixed width; use %% or em" % n); break
    return probs
