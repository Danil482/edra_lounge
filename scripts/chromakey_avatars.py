"""Remove green (#00FF00) background from avatar PNGs and resize to 533x800."""

from pathlib import Path
import numpy as np
from PIL import Image

SRC_DIR = Path(__file__).resolve().parent.parent / "frontend" / "assets" / "avatar" / "first_version"
DST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "assets" / "avatar"
TARGET_W, TARGET_H = 533, 800

MAPPING = {
    "ChatGPT Image May 19, 2026, 03_25_36 PM (1).png": "edra-idle.png",
    "ChatGPT Image May 19, 2026, 03_25_36 PM (2).png": "edra-greeting.png",
    "ChatGPT Image May 19, 2026, 03_25_37 PM (3).png": "edra-interested-low.png",
    "ChatGPT Image May 19, 2026, 03_25_37 PM (4).png": "edra-interested-high.png",
    "ChatGPT Image May 19, 2026, 03_25_37 PM (5).png": "edra-thinking.png",
    "ChatGPT Image May 19, 2026, 03_25_37 PM (6).png": "edra-excited.png",
    "ChatGPT Image May 19, 2026, 03_25_38 PM (7).png": "edra-surprised.png",
    "ChatGPT Image May 19, 2026, 03_25_38 PM (8).png": "edra-sad.png",
    "ChatGPT Image May 19, 2026, 03_25_38 PM (9).png": "edra-disappointed-low.png",
    "ChatGPT Image May 19, 2026, 03_25_40 PM (10).png": "edra-disappointed-high.png",
    "ChatGPT Image May 19, 2026, 03_25_48 PM (1).png": "edra-skeptical-low.png",
    "ChatGPT Image May 19, 2026, 03_25_48 PM (2).png": "edra-skeptical-high.png",
}

GREEN_THRESHOLD = 80
EDGE_FEATHER = 2


def remove_green(img: Image.Image) -> Image.Image:
    rgba = img.convert("RGBA")
    data = np.array(rgba, dtype=np.float32)
    r, g, b, a = data[:, :, 0], data[:, :, 1], data[:, :, 2], data[:, :, 3]

    green_mask = (g > 100) & (g > r + GREEN_THRESHOLD) & (g > b + GREEN_THRESHOLD)

    green_ratio = g / (r + b + 1)
    soft_alpha = np.clip((1.0 - (green_ratio - 1.0) / 2.0) * 255, 0, 255)

    new_alpha = np.where(green_mask, 0, a)

    from scipy.ndimage import binary_dilation
    border = binary_dilation(green_mask, iterations=EDGE_FEATHER) & ~green_mask
    new_alpha = np.where(border, np.minimum(new_alpha, soft_alpha), new_alpha)

    data[:, :, 3] = new_alpha
    return Image.fromarray(data.astype(np.uint8))


def process_all():
    try:
        from scipy.ndimage import binary_dilation  # noqa: F401
        has_scipy = True
    except ImportError:
        has_scipy = False

    for src_name, dst_name in MAPPING.items():
        src_path = SRC_DIR / src_name
        dst_path = DST_DIR / dst_name

        if not src_path.exists():
            print(f"SKIP {src_name} — not found")
            continue

        img = Image.open(src_path)

        if has_scipy:
            result = remove_green(img)
        else:
            result = remove_green_simple(img)

        result = result.resize((TARGET_W, TARGET_H), Image.LANCZOS)
        result.save(dst_path, "PNG")

        transparent = np.sum(np.array(result)[:, :, 3] == 0)
        total = TARGET_W * TARGET_H
        print(f"{dst_name}: {transparent}/{total} transparent pixels ({100*transparent/total:.1f}%)")


def remove_green_simple(img: Image.Image) -> Image.Image:
    rgba = img.convert("RGBA")
    data = np.array(rgba, dtype=np.float32)
    r, g, b, a = data[:, :, 0], data[:, :, 1], data[:, :, 2], data[:, :, 3]

    green_mask = (g > 100) & (g > r + GREEN_THRESHOLD) & (g > b + GREEN_THRESHOLD)

    green_ratio = g / (r + b + 1)
    soft_alpha = np.clip((1.0 - (green_ratio - 1.0) / 2.0) * 255, 0, 255)

    semi_green = (g > 80) & (g > r + 40) & (g > b + 40) & ~green_mask
    new_alpha = np.where(green_mask, 0, a)
    new_alpha = np.where(semi_green, np.minimum(new_alpha, soft_alpha), new_alpha)

    data[:, :, 3] = new_alpha
    return Image.fromarray(data.astype(np.uint8))


if __name__ == "__main__":
    process_all()
