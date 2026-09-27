"""Step 4: PNG rasterization and WebP optimization based on cfg.py configurations."""

import importlib.util
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image

FALLBACK_DEFAULT_BASE_WIDTH: int = 2560
FALLBACK_DEFAULT_RESOLUTION: Tuple[int, int] = (2560, 1440)
FALLBACK_WEBP_QUALITY: int = 90
FALLBACK_WEBP_LOSSLESS: bool = False


def get_svg_aspect_ratio(svg_file: Path) -> Optional[Tuple[float, float]]:
    try:
        tree = ET.parse(str(svg_file))
        root = tree.getroot()

        vb = root.get("viewBox")
        if vb:
            parts = [float(p) for p in re.split(r"[\s,]+", vb.strip()) if p]
            if len(parts) == 4 and parts[2] > 0 and parts[3] > 0:
                return parts[2], parts[3]

        w_str = root.get("width")
        h_str = root.get("height")
        if w_str and h_str:
            w = float(re.sub(r"[a-zA-Z%]+$", "", w_str.strip()))
            h = float(re.sub(r"[a-zA-Z%]+$", "", h_str.strip()))
            if w > 0 and h > 0:
                return w, h
    except Exception:
        pass
    return None


def calculate_target_resolution(
    svg_file: Path,
    resolutions: Dict[str, Tuple[int, int]],
    base_width: int,
    default_res: Tuple[int, int],
) -> Tuple[Tuple[int, int], str]:
    if svg_file.name in resolutions:
        return resolutions[svg_file.name], "vlastní z cfg.py"

    dims = get_svg_aspect_ratio(svg_file)
    if dims:
        orig_w, orig_h = dims
        calc_w = base_width
        calc_h = int(round(base_width * (orig_h / orig_w)))

        ratio_label = (
            "1:1"
            if abs(orig_w - orig_h) < 1e-5
            else f"{orig_w:.2f}:{orig_h:.2f}".rstrip("0").rstrip(".")
        )
        return (calc_w, calc_h), f"dynamické (poměr {ratio_label}, 2K báze)"

    return default_res, "výchozí 2K fallback"


def load_config(
    cfg_path: Path,
) -> Tuple[Dict[str, Tuple[int, int]], int, Tuple[int, int], int, bool]:
    resolutions: Dict[str, Tuple[int, int]] = {}
    base_width = FALLBACK_DEFAULT_BASE_WIDTH
    default_res = FALLBACK_DEFAULT_RESOLUTION
    webp_quality = FALLBACK_WEBP_QUALITY
    webp_lossless = FALLBACK_WEBP_LOSSLESS

    if cfg_path.is_file():
        try:
            spec = importlib.util.spec_from_file_location("branding_cfg", str(cfg_path))
            if spec and spec.loader:
                cfg_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(cfg_module)

                resolutions = getattr(cfg_module, "RESOLUTIONS", {}) or getattr(
                    cfg_module, "CONFIG", {}
                )
                base_width = getattr(
                    cfg_module, "DEFAULT_BASE_WIDTH", FALLBACK_DEFAULT_BASE_WIDTH
                )
                default_res = getattr(
                    cfg_module, "DEFAULT_RESOLUTION", FALLBACK_DEFAULT_RESOLUTION
                )
                webp_quality = getattr(
                    cfg_module, "WEBP_QUALITY", FALLBACK_WEBP_QUALITY
                )
                webp_lossless = getattr(
                    cfg_module, "WEBP_LOSSLESS", FALLBACK_WEBP_LOSSLESS
                )
                print(f"  📋 Načtena konfigurace z: {cfg_path.name}")
        except Exception as e:
            print(
                f"  ⚠️  Chyba při načítání '{cfg_path.name}': {e}. Použijí se výchozí hodnoty."
            )
    else:
        print(
            f"  ℹ️  Soubor '{cfg_path.name}' nebyl nalezen. Použijí se výchozí hodnoty."
        )

    return resolutions, base_width, default_res, webp_quality, webp_lossless


def rasterize_with_cairosvg(
    svg_file: Path, png_file: Path, width: int, height: int
) -> bool:
    try:
        import cairosvg

        cairosvg.svg2png(
            url=str(svg_file),
            write_to=str(png_file),
            output_width=width,
            output_height=height,
        )
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"  ⚠️  CairoSVG selhalo pro '{svg_file.name}': {e}. Zkouším Inkscape...")
        return False


def rasterize_with_inkscape(
    svg_file: Path, png_file: Path, width: int, height: int
) -> bool:
    inkscape_bin = shutil.which("inkscape")
    if not inkscape_bin:
        print("  ❌ Ani CairoSVG ani Inkscape nejsou dostupné pro rasterizaci.")
        return False

    cmd = [
        inkscape_bin,
        str(svg_file),
        "-o",
        str(png_file),
        "-w",
        str(width),
        "-h",
        str(height),
    ]

    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=120,
        )
        if res.returncode == 0 and png_file.is_file() and png_file.stat().st_size > 0:
            return True
        print(f"  ❌ Inkscape rasterizace selhala: {res.stderr.strip()}")
        return False
    except Exception as e:
        print(f"  ❌ Chyba při spuštění Inkscape rasterizace: {e}")
        return False


def rasterize_svg(svg_file: Path, png_file: Path, width: int, height: int) -> bool:
    if rasterize_with_cairosvg(svg_file, png_file, width, height):
        return True
    return rasterize_with_inkscape(svg_file, png_file, width, height)


def convert_to_webp(
    png_file: Path, webp_file: Path, quality: int, lossless: bool
) -> bool:
    """Převede PNG do WebP s maximální kompresí (method=6)."""
    try:
        webp_file.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(png_file) as img:
            img.save(
                webp_file,
                format="WEBP",
                quality=quality,
                lossless=lossless,
                method=6,
            )
        return True
    except Exception as e:
        print(f"  ❌ Chyba při převodu do WebP pro '{png_file.name}': {e}")
        return False


def run(
    svg_dir: Path, png_dir: Path, webp_dir: Path, cfg_path: Path
) -> Dict[str, List[Path]]:
    print(f"\n🖼️  [Krok 4] Rasterizace do PNG a WebP podle '{cfg_path.name}'...")
    resolutions, base_width, default_res, webp_quality, webp_lossless = load_config(
        cfg_path
    )

    png_dir.mkdir(parents=True, exist_ok=True)
    webp_dir.mkdir(parents=True, exist_ok=True)

    svg_files = sorted(svg_dir.glob("*.svg"))
    if not svg_files:
        print(f"  ℹ️  V '{svg_dir}' nebyly nalezeny žádné SVG soubory.")
        return {"png": [], "webp": []}

    generated_pngs: List[Path] = []
    generated_webps: List[Path] = []

    for svg_file in svg_files:
        png_file = png_dir / f"{svg_file.stem}.png"
        webp_file = webp_dir / f"{svg_file.stem}.webp"

        (width, height), config_source = calculate_target_resolution(
            svg_file, resolutions, base_width, default_res
        )

        print(
            f"  📐 {svg_file.name} -> PNG & WebP [{width}x{height} px, {config_source}]"
        )

        if rasterize_svg(svg_file, png_file, width, height):
            png_size_kb = png_file.stat().st_size / 1024
            print(f"  ✅ PNG: png/{png_file.name} ({png_size_kb:.1f} KiB)")
            generated_pngs.append(png_file)

            if convert_to_webp(png_file, webp_file, webp_quality, webp_lossless):
                webp_size_kb = webp_file.stat().st_size / 1024
                saved = (
                    ((png_size_kb - webp_size_kb) / png_size_kb * 100)
                    if png_size_kb > 0
                    else 0
                )
                print(
                    f"  ✅ WebP optimalizováno: webp/{webp_file.name} "
                    f"({webp_size_kb:.1f} KiB, úspora oproti PNG {saved:.1f}%)"
                )
                generated_webps.append(webp_file)
        else:
            print(f"  ❌ Nepodařilo se vygenerovat výstupy pro: {svg_file.name}")

    return {"png": generated_pngs, "webp": generated_webps}


if __name__ == "__main__":
    base_path = Path(__file__).resolve().parent.parent
    run(
        base_path / "output" / "svg",
        base_path / "output" / "png",
        base_path / "output" / "webp",
        base_path / "cfg.py",
    )
