"""Fix the AI images where they contradict the script, then upscale for zooms.

- scene4: repaint the smartboard (the AI drew an unrelated 1760-1991 timeline)
  with the script's 1830s - 1857 - 1870s timeline, keeping the student's arm
  and head in front of it via a hand-drawn mask.
- scene5: put the script's text on the framed notice.
Writes build/images/<id>_fixed.png (2x upscaled, for sharper camera moves).
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

B = Path(__file__).parent / "build" / "images"
SANS_B = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
SANS_SB = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
SERIF_B = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"


def font(path, size):
    return ImageFont.truetype(path, size)


def perspective_coeffs(src, dst):
    """Coefficients for Image.transform(PERSPECTIVE) mapping dst quad -> src quad."""
    m = []
    for (x, y), (u, v) in zip(dst, src):
        m.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); m.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    a = np.array(m, dtype=float); b = np.array([c for p in src for c in p], dtype=float)
    return np.linalg.solve(a, b).tolist()


def board_scene4(img):
    W, H = 1000, 760
    board = Image.new("RGB", (W, H))
    top, bot = np.array([22, 40, 72]), np.array([30, 58, 98])
    grad = (top + (bot - top) * np.linspace(0, 1, H)[:, None]).astype(np.uint8)
    board = Image.fromarray(np.repeat(grad[:, None, :], W, axis=1))
    d = ImageDraw.Draw(board, "RGBA")
    for x in range(0, W, 50):
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, 10))
    for y in range(0, H, 50):
        d.line([(0, y), (W, y)], fill=(255, 255, 255, 10))
    d.text((40, 42), "RESISTANCE IN INDIA", font=font(SANS_B, 46), fill=(235, 242, 255))
    d.text((40, 100), "Peasant & tribal India — not just the North", font=font(SANS_SB, 26), fill=(150, 190, 235))
    d.rounded_rectangle((760, 36, 960, 90), 27, outline=(140, 200, 255), width=3)
    d.text((860, 63), "TIMELINE", font=font(SANS_B, 26), fill=(190, 225, 255), anchor="mm")
    # timeline in the lower-left part, which the student's body doesn't hide
    y, xs = 520, [105, 320, 560]
    glow = Image.new("RGBA", (W, H)); g = ImageDraw.Draw(glow)
    g.rounded_rectangle((xs[0] - 10, y - 26, xs[2] + 10, y + 26), 26, fill=(255, 190, 20, 150))
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    board.paste(glow, (0, 0), glow)
    d.line([(30, y), (980, y)], fill=(70, 170, 255), width=6)
    d.rounded_rectangle((xs[0] - 4, y - 15, xs[2] + 4, y + 15), 15, fill=(255, 196, 40))
    for x, lab, sub in zip(xs, ["1830s", "1857", "1870s"], ["Risings begin", "The Great Rebellion", "Still resisting"]):
        d.ellipse((x - 16, y - 16, x + 16, y + 16), fill=(255, 255, 255), outline=(255, 170, 0), width=5)
        d.text((x, y + 62), lab, font=font(SANS_B, 50), fill=(255, 255, 255), anchor="mm")
        d.text((x, y + 112), sub, font=font(SANS_SB, 24), fill=(170, 205, 240), anchor="mm")
    # screen corners in the photo (TL, TR, BR, BL)
    quad = [(253, 223), (1043, 140), (1043, 857), (253, 831)]
    coeffs = perspective_coeffs([(0, 0), (W, 0), (W, H), (0, H)], quad)
    warped = board.transform(img.size, Image.PERSPECTIVE, coeffs, Image.BICUBIC)
    screen = Image.new("L", img.size, 0)
    ImageDraw.Draw(screen).polygon(quad, fill=255)
    # the student in front of the screen (crop coords from a 200,100 offset at 4/3 scale)
    pts = [(305, 283), (310, 272), (325, 280), (345, 298), (362, 318), (380, 335), (410, 345), (445, 342),
           (455, 300), (452, 262), (470, 230), (510, 213), (560, 220), (595, 250), (600, 300), (585, 345),
           (600, 380), (612, 430), (620, 600), (430, 600), (420, 480), (400, 385), (375, 360), (352, 345),
           (335, 330), (318, 305)]
    outline = Image.new("L", img.size, 0)
    ImageDraw.Draw(outline).polygon([(200 + x * 4 / 3, 100 + y * 4 / 3) for x, y in pts], fill=255)
    outline = outline.filter(ImageFilter.MaxFilter(9))
    # inside the outline, the person is whatever isn't board-blue (hair, skin, grey hoodie)
    a = np.array(img).astype(int)
    not_board = ((a[..., 2] - a[..., 0]) < 16).astype(np.uint8) * 255
    person = np.minimum(np.array(outline), not_board).astype(np.uint8)
    person = Image.fromarray(person).filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(1.2))
    mask = Image.fromarray(np.minimum(np.array(screen), 255 - np.array(person)).astype(np.uint8))
    out = img.copy(); out.paste(warped, (0, 0), mask)
    return out


def notice_scene5(img):
    out = img.copy()
    box = (372, 312, 712, 432)  # lower part of the notice paper, under "CLUB NOTICE - 1858"
    a = np.array(img).astype(float)
    x0, y0, x1, y1 = box
    # rebuild the paper by blending the clean rows just above and below the old text
    above = np.median(a[y0 - 6:y0, x0:x1], axis=0); below = np.median(a[y1:y1 + 6, x0:x1], axis=0)
    t = np.linspace(0, 1, y1 - y0)[:, None, None]
    paper = above[None] * (1 - t) + below[None] * t
    paper = np.array(Image.fromarray(paper.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))).astype(float)
    paper += np.random.default_rng(1).normal(0, 2.5, paper.shape[:2])[..., None]
    fill = Image.fromarray(paper.clip(0, 255).astype(np.uint8))
    m = Image.new("L", fill.size, 0); ImageDraw.Draw(m).rectangle((4, 4, fill.width - 5, fill.height - 5), fill=255)
    out.paste(fill, box[:2], m.filter(ImageFilter.GaussianBlur(3)))
    d = ImageDraw.Draw(out)
    ink = (52, 36, 22)
    cx = (box[0] + box[2]) / 2
    d.text((cx, 340), "1829: SATI BANNED.", font=font(SERIF_B, 18), fill=ink, anchor="mm")
    d.text((cx, 376), "1856: WIDOW REMARRIAGE", font=font(SERIF_B, 18), fill=ink, anchor="mm")
    d.text((cx, 404), "ALLOWED.", font=font(SERIF_B, 18), fill=ink, anchor="mm")
    return out


FIXES = {"scene4": board_scene4, "scene5": notice_scene5}
for n in range(1, 6):
    sid = f"scene{n}"
    img = Image.open(B / f"{sid}.png").convert("RGB")
    if sid in FIXES:
        img = FIXES[sid](img)
    img.resize((img.width * 2, img.height * 2), Image.LANCZOS).save(B / f"{sid}_fixed.png")
    print(sid, "ok")
