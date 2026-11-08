"""Self-contained Kindle bar chart. Matplotlib and Pillow only.

Tier C agents can return a script like this. Do not claim it was rendered or
checked unless you actually ran it. Data below are fictional.
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

TONES = (0, 85, 153, 221, 255)
# Printed estimates / values. This table is the text fallback.
ROWS = (("North", 96, True), ("Central", 64, False), ("South", 40, False))
SOURCE = "Source: Fictional example data, 2025."


def quantize(image):
    lut = [min(TONES, key=lambda tone: abs(tone - value)) for value in range(256)]
    return image.convert("L").point(lut)


def render(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(4.12, 4.12), dpi=300, facecolor="white")
    ax = fig.add_axes([0.08, 0.16, 0.84, 0.68])
    labels = [row[0] for row in ROWS]
    values = [row[1] for row in ROWS]
    colors = ["#000000" if row[2] else "#999999" for row in ROWS]
    positions = list(range(len(ROWS) - 1, -1, -1))
    ax.barh(positions, values, color=colors, height=0.55)
    ax.set_yticks(positions)
    ax.set_yticklabels(labels, fontsize=11)
    ax.set_xlim(0, 110)
    ax.set_xlabel("")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0, labelsize=9.5, colors="#555555")
    ax.axvline(0, color="#000000", lw=1.5)
    for guide in (25, 50, 75, 100):
        ax.axvline(guide, color="#DDDDDD", lw=1.5, zorder=0)
    for y, value, focal in zip(positions, values, [row[2] for row in ROWS]):
        ax.text(value + 1.5, y, str(value), va="center", fontsize=11,
                fontweight="bold" if focal else "normal", color="#000000" if focal else "#555555")
    fig.text(0.08, 0.90, "North leads December at 96.", fontsize=13, fontweight="bold")
    fig.text(0.08, 0.845, "December shipments, thousands · 2025", fontsize=10.5, color="#555555")
    fig.text(0.08, 0.04, SOURCE, fontsize=9.5, color="#555555")
    fig.savefig(path, dpi=300, facecolor="white")
    plt.close(fig)
    image = quantize(Image.open(path))
    if image.width != 1236:
        image = image.resize((1236, round(image.height * 1236 / image.width)), Image.Resampling.LANCZOS)
        image = quantize(image)
    image.save(path, optimize=True)
    print("\n".join("%s\t%s" % (label, value) for label, value, _focal in ROWS))
    print(SOURCE)
    print("wrote", path)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    default = Path(__file__).resolve().parent / "output" / "matplotlib-only.png"
    parser.add_argument("--out", type=Path, default=default)
    args = parser.parse_args(argv)
    render(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
