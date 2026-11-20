#!/usr/bin/env python3
"""Convert the skill's Markdown document (with images) into a .docx with embedded screenshots.

Usage:  python build_doc.py document.md [-o document.docx]

Supported Markdown: # headings, paragraphs, **bold**, *italic*, `code`, [links](url),
- / * / 1. lists (one level of nesting via 2+ space indent), > quotes, ``` code blocks,
| tables |, --- rules, and images on their own line: ![caption](path).
A line directly under an image starting with `*` and ending with `*` is treated as its caption.
"""
import argparse
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

INLINE_RE = re.compile(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|_[^_\s][^_]*_|`[^`]+`|\[[^\]]+\]\([^)]+\))")
IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)\s*$")


def add_hyperlink(paragraph, text, url):
    part = paragraph.part
    r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                          is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0563C1")
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    rpr.append(color)
    rpr.append(underline)
    run.append(rpr)
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    run.append(t)
    link.append(run)
    paragraph._p.append(link)


def add_inline(paragraph, text):
    for piece in INLINE_RE.split(text):
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**"):
            paragraph.add_run(piece[2:-2]).bold = True
        elif piece.startswith("`") and piece.endswith("`"):
            r = paragraph.add_run(piece[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(9.5)
        elif piece.startswith("[") and "](" in piece:
            m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", piece)
            if m.group(2).startswith(("http://", "https://", "mailto:")):
                add_hyperlink(paragraph, m.group(1), m.group(2))
            else:
                paragraph.add_run(m.group(1))
        elif len(piece) > 2 and piece[0] == piece[-1] and piece[0] in "*_":
            paragraph.add_run(piece[1:-1]).italic = True
        else:
            paragraph.add_run(piece)


def shade(cell, hex_fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


def add_table(doc, rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    cells = [r for r in cells if not all(re.fullmatch(r":?-{2,}:?", c) for c in r if c)]
    if not cells:
        return
    ncol = max(len(r) for r in cells)
    table = doc.add_table(rows=len(cells), cols=ncol)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, r in enumerate(cells):
        for j in range(ncol):
            cell = table.cell(i, j)
            p = cell.paragraphs[0]
            add_inline(p, r[j] if j < len(r) else "")
            for run in p.runs:
                run.font.size = Pt(10)
                if i == 0:
                    run.bold = True
            if i == 0:
                shade(cell, "D9E2F3")
    doc.add_paragraph()


def add_image(doc, md_dir, src, caption, max_width_in):
    path = (md_dir / src).resolve()
    if not path.exists():
        print(f"WARNING: image not found, skipped: {src}", file=sys.stderr)
        doc.add_paragraph(f"[missing image: {src}]")
        return False
    try:
        from PIL import Image
        with Image.open(path) as im:
            w, h = im.size
        width = min(max_width_in, w / 96)
        if h / w * width > 7.0:  # keep very tall images on one page
            width = 7.0 * w / h
    except Exception:
        width = max_width_in
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Inches(width))
    if caption:
        cp = doc.add_paragraph()
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_inline(cp, caption)
        for run in cp.runs:
            run.italic = True
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
    return True


def convert(md_path, out_path):
    md_dir = md_path.parent
    lines = md_path.read_text(encoding="utf-8").splitlines()
    doc = Document()
    sec = doc.sections[0]
    for side in ("left_margin", "right_margin"):
        setattr(sec, side, Inches(0.9))
    max_img_w = (sec.page_width - sec.left_margin - sec.right_margin) / 914400
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)

    i, images, missing = 0, 0, 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("```"):
            buf = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            p = doc.add_paragraph()
            r = p.add_run("\n".join(buf))
            r.font.name = "Consolas"
            r.font.size = Pt(9)
            p.paragraph_format.left_indent = Inches(0.25)
            i += 1
            continue

        m = IMAGE_RE.match(stripped)
        if m:
            caption = m.group(1)
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if len(nxt) > 2 and nxt[0] == nxt[-1] and nxt[0] in "*_" and not nxt.startswith("**"):
                caption = nxt[1:-1]
                i += 1
            ok = add_image(doc, md_dir, m.group(2), caption, max_img_w)
            images += ok
            missing += not ok
            i += 1
            continue

        hm = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if hm:
            level = len(hm.group(1))
            text = hm.group(2).strip()
            if level == 1 and not any(p.text for p in doc.paragraphs):
                doc.add_heading(text, level=0)
            else:
                h = doc.add_heading(level=min(level, 9))
                add_inline(h, text)
            i += 1
            continue

        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", stripped):
            p = doc.add_paragraph()
            p_pr = p._p.get_or_add_pPr()
            bdr = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "BFBFBF")):
                bottom.set(qn(k), v)
            bdr.append(bottom)
            p_pr.append(bdr)
            i += 1
            continue

        if stripped.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i])
                i += 1
            add_table(doc, rows)
            continue

        if stripped.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            p = doc.add_paragraph(style="Intense Quote")
            add_inline(p, " ".join(buf))
            continue

        lm = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)", line)
        if lm:
            indent = len(lm.group(1).replace("\t", "    "))
            ordered = lm.group(2)[0].isdigit()
            style = "List Number" if ordered else "List Bullet"
            if indent >= 2:
                style += " 2"
            text = lm.group(3)
            cb = re.match(r"^\[( |x|X)\]\s+(.*)", text)
            if cb:
                text = ("☑ " if cb.group(1).lower() == "x" else "☐ ") + cb.group(2)
            p = doc.add_paragraph(style=style)
            add_inline(p, text)
            i += 1
            continue

        buf = [stripped]
        i += 1
        while i < len(lines):
            s = lines[i].strip()
            if (not s or s.startswith(("#", "|", ">", "```", "![")) or re.match(r"^\s*([-*+]|\d+[.)])\s+", lines[i])
                    or re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s)):
                break
            buf.append(s)
            i += 1
        p = doc.add_paragraph()
        add_inline(p, " ".join(buf))

    doc.save(out_path)
    return images, missing


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("markdown")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()
    md = Path(args.markdown).resolve()
    out = Path(args.out).resolve() if args.out else md.with_suffix(".docx")
    images, missing = convert(md, out)
    print(f"wrote {out}  ({images} images embedded, {missing} missing)")
    if missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
