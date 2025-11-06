#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_images.py
Remove background & export to WebP with polishing options for a uniform fridge grid.

Usage examples:
    python process_images.py --canvas 900 --pad 40 --bg transparent --shadow --outline 2 --overwrite
    python process_images.py --canvas 900 --bg "#f8f9fa" --shadow --shadow-blur 22 --outline 3
"""

import argparse
import io
from pathlib import Path
import sys
from typing import Tuple

from PIL import Image, ImageOps, ImageFilter, ImageChops
from tqdm import tqdm
from rembg import remove
from rembg.session_factory import new_session

# --- HEIC/HEIF support --------------------------------------------------------
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_ENABLED = True
except Exception:
    HEIF_ENABLED = False

SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
if HEIF_ENABLED:
    SUPPORTED_EXT |= {".heic", ".heif"}


# ------------------------------------------------------------------------------
def load_image(path: Path) -> Image.Image:
    """Charge une image en respectant l’orientation EXIF et force RGBA."""
    with path.open("rb") as f:
        img = Image.open(io.BytesIO(f.read()))
        img.load()
    img = ImageOps.exif_transpose(img).convert("RGBA")
    return img


def resize_max(img: Image.Image, max_side: int | None) -> Image.Image:
    """Redimensionne en conservant le ratio, sans dépasser max_side."""
    if not max_side:
        return img
    w, h = img.size
    scale = min(max_side / max(w, h), 1.0)
    if scale < 1.0:
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        img = img.resize(new_size, Image.LANCZOS)
    return img


# ------------------------- Finitions visuelles (optionnelles) -----------------
def fit_to_canvas(img: Image.Image, size: int, pad: int = 40, background=(0, 0, 0, 0)) -> Image.Image:
    """Place l’image centrée sur un canvas carré size×size, avec padding."""
    canvas = Image.new("RGBA", (size, size), background)
    w, h = img.size
    scale = min((size - 2 * pad) / w, (size - 2 * pad) / h, 1.0)
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    img_resized = img.resize(new_size, Image.LANCZOS)
    ox = (size - new_size[0]) // 2
    oy = (size - new_size[1]) // 2
    canvas.alpha_composite(img_resized, (ox, oy))
    return canvas


def add_drop_shadow(img: Image.Image, offset_x: int = 0, offset_y: int = 12, blur: int = 18, opacity: int = 90) -> Image.Image:
    """
    Ajoute une ombre douce sous l’objet (utilise le canal alpha).
    offset_x, offset_y: décalage de l'ombre en px
    blur: rayon Gaussian blur
    opacity: 0-255
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    w, h = img.size
    alpha = img.split()[-1]

    # create shadow base
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    shadow_layer = Image.new("RGBA", (w, h), (0, 0, 0, opacity))

    # offset the alpha mask to position the shadow
    shadow_mask = ImageChops.offset(alpha, offset_x, offset_y)
    shadow.paste(shadow_layer, mask=shadow_mask)
    if blur > 0:
        shadow = shadow.filter(ImageFilter.GaussianBlur(blur))

    base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    base.alpha_composite(shadow)
    base.alpha_composite(img)
    return base


def add_outline(img: Image.Image, width: int = 2, color: Tuple[int, int, int, int] = (230, 230, 230, 255)) -> Image.Image:
    """Ajoute un fin liseré autour de l’objet pour améliorer la lisibilité."""
    if width <= 0:
        return img
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    w, h = img.size
    alpha = img.split()[-1]

    # make thicker mask by repeated MaxFilter
    outline = alpha
    for _ in range(width):
        outline = outline.filter(ImageFilter.MaxFilter(3))

    border = Image.new("RGBA", (w, h), color)
    border.putalpha(outline)

    out = Image.alpha_composite(border, img)
    return out


def parse_color(s: str) -> Tuple[int, int, int, int]:
    """Parse '#RRGGBB' / '#RRGGBBAA' ou 'transparent' -> tuple RGBA."""
    if s.lower() == "transparent":
        return (0, 0, 0, 0)
    s = s.lstrip("#")
    if len(s) == 6:
        r = int(s[0:2], 16); g = int(s[2:4], 16); b = int(s[4:6], 16)
        return (r, g, b, 255)
    if len(s) == 8:
        r = int(s[0:2], 16); g = int(s[2:4], 16); b = int(s[4:6], 16); a = int(s[6:8], 16)
        return (r, g, b, a)
    raise ValueError("Couleur invalide (utilise '#RRGGBB', '#RRGGBBAA' ou 'transparent').")


# ------------------------------------------------------------------------------
def process_one(
    path: Path,
    inp_dir: Path,
    out_dir: Path,
    session,
    quality: int,
    max_side: int | None,
    suffix: str,
    overwrite: bool,
    canvas_size: int | None,
    pad: int,
    bg_color: Tuple[int, int, int, int],
    use_shadow: bool,
    shadow_offset_x: int,
    shadow_offset_y: int,
    shadow_blur: int,
    shadow_opacity: int,
    outline_px: int,
    outline_color: Tuple[int, int, int, int],
    outline_before_canvas: bool,
    verbose: bool = False,
):
    """Traite un fichier: détourage -> resize -> finitions -> WebP."""
    try:
        # Construit le chemin de sortie en conservant l’arborescence
        rel = path.relative_to(inp_dir)
        rel = rel.with_suffix("")  # remove extension
        rel = Path(str(rel) + suffix).with_suffix(".webp")
        out_path = out_dir / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if out_path.exists() and not overwrite:
            if verbose:
                print(f"skipped (exists): {out_path}")
            return True, out_path, "skipped"

        # 1) Chargement
        inp = load_image(path)

        # 2) Détourage
        cut = remove(inp, session=session)

        # 3) Resize max (avant finitions)
        cut = resize_max(cut, max_side)

        # 4) Finitions optionnelles
        # Outline before canvas (useful if you want outline to follow original mask)
        if outline_before_canvas and outline_px and outline_px > 0:
            cut = add_outline(cut, width=outline_px, color=outline_color)

        if use_shadow:
            cut = add_drop_shadow(cut, offset_x=shadow_offset_x, offset_y=shadow_offset_y, blur=shadow_blur, opacity=shadow_opacity)

        # Fit to canvas AFTER shadow so shadow is included in canvas composition
        if canvas_size:
            cut = fit_to_canvas(cut, size=canvas_size, pad=pad, background=bg_color)

        # Outline AFTER canvas (if requested and not applied before)
        if not outline_before_canvas and outline_px and outline_px > 0:
            cut = add_outline(cut, width=outline_px, color=outline_color)

        # 5) Export WebP (transparence, bords propres)
        cut.save(out_path, "WEBP", quality=quality, method=6, exact=True)
        if verbose:
            print(f"written: {out_path} (size={cut.size})")
        return True, out_path, "written"

    except Exception as e:
        if verbose:
            print(f"error processing {path}: {e}")
        return False, f"{path}: {e}", "error"


# ------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Remove background & export to WebP (avec finitions optionnelles).")
    ap.add_argument("--in", dest="inp", default="images", help="Dossier d'entrée (défaut: images)")
    ap.add_argument("--out", dest="out", default="out", help="Dossier de sortie (défaut: out)")
    ap.add_argument("--quality", type=int, default=85, help="Qualité WebP 0-100 (défaut 85)")
    ap.add_argument("--max-side", type=int, default=None, help="Redimensionner (côté max en px), ex: 1600")
    ap.add_argument("--model", default="isnet-general-use", help="Modèle rembg (défaut: isnet-general-use)")
    ap.add_argument("--suffix", default="", help="Suffixe ajouté au nom (ex: _cut)")
    ap.add_argument("--overwrite", action="store_true", help="Réécrire les fichiers déjà traités")

    # Options d’uniformisation visuelle pour le “fridge grid”
    ap.add_argument("--canvas", type=int, default=None, help="Canvas carré final (ex: 900)")
    ap.add_argument("--pad", type=int, default=40, help="Padding intérieur (défaut 40)")
    ap.add_argument("--bg", default="transparent", help="Couleur canvas: '#RRGGBB' / '#RRGGBBAA' / 'transparent'")

    # shadow options
    ap.add_argument("--shadow", action="store_true", help="Ajouter une ombre douce")
    ap.add_argument("--shadow-offset-x", type=int, default=0, help="Décalage X de l'ombre (px)")
    ap.add_argument("--shadow-offset-y", type=int, default=12, help="Décalage Y de l'ombre (px)")
    ap.add_argument("--shadow-blur", type=int, default=18, help="Blur radius pour l'ombre")
    ap.add_argument("--shadow-opacity", type=int, default=90, help="Opacité ombre (0-255)")

    # outline options
    ap.add_argument("--outline", type=int, default=0, help="Épaisseur du liseré (0=off)")
    ap.add_argument("--outline-color", default="#E6E6E6", help="Couleur du liseré (hex), ex: '#E6E6E6'")
    ap.add_argument("--outline-before-canvas", action="store_true", help="Appliquer le liseré AVANT le centrage sur le canvas")

    ap.add_argument("--verbose", action="store_true", help="Mode verbeux")

    args = ap.parse_args()

    inp_dir = Path(args.inp)
    out_dir = Path(args.out)

    if not inp_dir.exists():
        raise SystemExit(f"Dossier introuvable: {inp_dir}")

    if not HEIF_ENABLED:
        # On ne bloque pas, mais on avertit si HEIC potentiels
        has_heic = any(p.suffix.lower() in {".heic", ".heif"} for p in inp_dir.rglob("*"))
        if has_heic:
            print("ℹ️  HEIC détecté, mais 'pillow-heif' n'est pas chargé. Installe-le avec: pip install pillow-heif")

    try:
        bg_color = parse_color(args.bg)
    except Exception as e:
        raise SystemExit(f"Couleur de fond invalide (--bg): {e}")

    try:
        outline_color = parse_color(args.outline_color)
    except Exception as e:
        raise SystemExit(f"Couleur outline invalide (--outline-color): {e}")

    # Session rembg (modèle)
    session = new_session(args.model)

    files = [p for p in inp_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXT]
    if not files:
        raise SystemExit(f"Aucune image trouvée dans {inp_dir}")

    ok = 0
    skipped = 0
    errors = 0
    for f in tqdm(files, desc="Processing", unit="img"):
        success, info, status = process_one(
            path=f,
            inp_dir=inp_dir,
            out_dir=out_dir,
            session=session,
            quality=args.quality,
            max_side=args.max_side,
            suffix=args.suffix,
            overwrite=args.overwrite,
            canvas_size=args.canvas,
            pad=args.pad,
            bg_color=bg_color,
            use_shadow=bool(args.shadow),
            shadow_offset_x=args.shadow_offset_x,
            shadow_offset_y=args.shadow_offset_y,
            shadow_blur=args.shadow_blur,
            shadow_opacity=max(0, min(255, args.shadow_opacity)),
            outline_px=args.outline,
            outline_color=outline_color,
            outline_before_canvas=bool(args.outline_before_canvas),
            verbose=bool(args.verbose),
        )
        if success:
            ok += 1
            if status == "skipped":
                skipped += 1
        else:
            errors += 1
            print("⚠️", info)

    written = ok - skipped
    print(
        f"\n✅ Terminé: {ok}/{len(files)} images traitées "
        f"(écrites: {written}, ignorées: {skipped}, erreurs: {errors})."
    )
    print(f"➡️  Sortie: {out_dir.resolve()}")


if __name__ == "__main__":
    main()