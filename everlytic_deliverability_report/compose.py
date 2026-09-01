"""Stitch per-panel PNGs into one image per template slot (Pillow)."""
import os

from PIL import Image

from .panels import SLOTS

GAP = 20
BG = (255, 255, 255)


def _load(panels_dir, stem, idx):
    return Image.open(os.path.join(panels_dir, f"{stem}__{idx}.png")).convert("RGB")


def _row(imgs, target_h):
    if target_h is None:
        target_h = imgs[0].height
    scaled = []
    for im in imgs:
        w = round(im.width * target_h / im.height)
        scaled.append(im.resize((w, target_h), Image.LANCZOS))
    total_w = sum(i.width for i in scaled) + GAP * (len(scaled) - 1)
    canvas = Image.new("RGB", (total_w, target_h), BG)
    x = 0
    for i in scaled:
        canvas.paste(i, (x, 0))
        x += i.width + GAP
    return canvas


def _grid2x2(imgs):
    w, h = imgs[0].size
    canvas = Image.new("RGB", (w * 2 + GAP, h * 2 + GAP), BG)
    for im, (x, y) in zip(imgs, [(0, 0), (w + GAP, 0), (0, h + GAP), (w + GAP, h + GAP)]):
        canvas.paste(im.resize((w, h), Image.LANCZOS), (x, y))
    return canvas


def compose_all(panels_dir, out_dir):
    """Build one final image per slot into out_dir. Returns {media_name: (w, h)}."""
    os.makedirs(out_dir, exist_ok=True)
    sizes = {}
    for slot in SLOTS:
        media = slot["media"]
        stem = media.rsplit(".", 1)[0]
        imgs = [_load(panels_dir, stem, i) for i in range(len(slot["panels"]))]
        layout = slot["layout"]
        if layout == "single":
            out = imgs[0]
        elif layout == "row":
            out = _row(imgs, slot.get("row_h"))
        elif layout == "grid2x2":
            out = _grid2x2(imgs)
        else:
            raise ValueError(f"unknown layout {layout!r} for {media}")
        out.save(os.path.join(out_dir, media))
        sizes[media] = out.size
    return sizes
