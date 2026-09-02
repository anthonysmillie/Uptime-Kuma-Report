"""Build the final .docx: swap panel images, true up their heights, and stamp dates.

Self-contained: reads the template with zipfile, edits word/document.xml with lxml,
writes a fresh .docx. No dependency on the office-skills plugin.
"""
import io
import os
import re
import zipfile
from typing import Dict, Tuple

from lxml import etree
from PIL import Image

from .panels import (
    EDITOR_REPLACEMENT,
    PROTECTED_MEDIA,
    TEMPLATE_EDITOR,
    TEMPLATE_TITLE_DATE,
    TEMPLATE_VERSION_DATE,
)

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
R_EMBED = f"{{{NS['r']}}}embed"


def _rid_to_media(rels_xml: bytes) -> Dict[str, str]:
    root = etree.fromstring(rels_xml)
    out = {}
    for rel in root:
        target = rel.get("Target", "")
        if "media/" in target and rel.get("Id"):
            out[rel.get("Id")] = target.split("media/")[-1]
    return out


def _fix_extents(doc: etree._Element, rid_media: Dict[str, str], final_sizes: Dict[str, Tuple[int, int]]):
    """For each drawing whose image is a swapped slot, keep cx and set cy = cx * h / w."""
    for drawing in doc.iter(f"{{{NS['w']}}}drawing"):
        blip = drawing.find(f".//{{{NS['a']}}}blip")
        if blip is None:
            continue
        rid = blip.get(R_EMBED)
        media = rid_media.get(rid)
        if media not in final_sizes:
            continue
        w, h = final_sizes[media]
        extent = drawing.find(f".//{{{NS['wp']}}}extent")
        aext = drawing.find(f".//{{{NS['a']}}}ext")
        if extent is None or aext is None:
            continue
        cx = int(extent.get("cx"))
        new_cy = str(round(cx * h / w))
        extent.set("cy", new_cy)
        aext.set("cy", new_cy)


def _rewrite_text(doc: etree._Element, replacements):
    """Replace fixed strings that may be char-split across consecutive <w:t> runs.

    replacements: list of (original, new). Scans w:t text nodes in document order and
    rewrites the minimal window whose concatenation equals `original`.
    """
    wts = list(doc.iter(f"{{{NS['w']}}}t"))
    counts = {orig: 0 for orig, _ in replacements}
    for original, new in replacements:
        i = 0
        while i < len(wts):
            acc = ""
            window = []
            j = i
            while j < len(wts) and len(acc) < len(original):
                acc += wts[j].text or ""
                window.append(wts[j])
                j += 1
            if acc == original:
                window[0].text = new
                for node in window[1:]:
                    node.text = ""
                counts[original] += 1
                i = j
            else:
                i += 1
    return counts


def build(template_path: str, final_dir: str, final_sizes: Dict[str, Tuple[int, int]],
          title_date: str, version_date: str, out_path: str) -> dict:
    """Assemble the report .docx. `title_date`/`version_date` are the run/generation date
    stamps (dd-mm-yyyy / dd/mm/yyyy). Returns a small report dict for logging."""
    with open(template_path, "rb") as f:
        template_bytes = f.read()

    zin = zipfile.ZipFile(io.BytesIO(template_bytes), "r")
    document_xml = zin.read("word/document.xml")
    rels_xml = zin.read("word/_rels/document.xml.rels")
    rid_media = _rid_to_media(rels_xml)
    media_rids = {v: k for k, v in rid_media.items()}

    # sanity: every slot we intend to swap must exist in the template, and never a protected asset
    for media in final_sizes:
        if media in PROTECTED_MEDIA:
            raise ValueError(f"refusing to overwrite protected media {media}")
        if media not in media_rids:
            raise ValueError(f"template has no relationship for {media}")

    doc = etree.fromstring(document_xml)
    _fix_extents(doc, rid_media, final_sizes)
    text_counts = _rewrite_text(doc, [
        (TEMPLATE_TITLE_DATE, title_date),
        (TEMPLATE_VERSION_DATE, version_date),
        (TEMPLATE_EDITOR, EDITOR_REPLACEMENT),
    ])
    new_document = etree.tostring(doc, xml_declaration=True, encoding="UTF-8", standalone=True)

    # write a fresh zip: copy every entry, overriding document.xml + swapped media
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            name = item.filename
            if name == "word/document.xml":
                data = new_document
            elif name.startswith("word/media/") and name.split("/")[-1] in final_sizes:
                with open(os.path.join(final_dir, name.split("/")[-1]), "rb") as mf:
                    data = mf.read()
            else:
                data = zin.read(name)
            zout.writestr(item, data)
    zin.close()
    with open(out_path, "wb") as f:
        f.write(buf.getvalue())

    return {"text_counts": text_counts, "swapped": sorted(final_sizes), "out": out_path}


def verify(out_path: str, expect_title_date: str, final_sizes: Dict[str, Tuple[int, int]]) -> None:
    """Post-build assertions; raises AssertionError on any mismatch."""
    z = zipfile.ZipFile(out_path, "r")
    document_xml = z.read("word/document.xml").decode("utf-8")
    text = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", document_xml))
    # dates: originals gone, run-date stamp present
    assert TEMPLATE_TITLE_DATE not in document_xml, "old title date still present"
    assert TEMPLATE_VERSION_DATE not in document_xml, "old version date still present"
    assert expect_title_date in text, "run-date stamp not found in document text"
    # editor: original name replaced with the generic label
    assert TEMPLATE_EDITOR not in text, f"old editor name {TEMPLATE_EDITOR!r} still present"
    assert EDITOR_REPLACEMENT in text, f"editor label {EDITOR_REPLACEMENT!r} not found"
    # swapped media embedded at expected byte size
    for media, _ in final_sizes.items():
        data = z.read(f"word/media/{media}")
        img = Image.open(io.BytesIO(data))
        assert img.size == final_sizes[media], f"{media} embedded at {img.size}, expected {final_sizes[media]}"
    z.close()
