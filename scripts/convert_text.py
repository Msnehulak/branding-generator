"""Step 2: Inkscape text-to-path conversion."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List


def convert_text_to_path(svg_file: Path, inkscape_bin: str = "inkscape") -> bool:
    """
    Execute Inkscape to convert all text in SVG to path outlines.
    Uses --export-text-to-path and --export-area-drawing.
    """
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        cmd = [
            inkscape_bin,
            str(svg_file),
            "--export-text-to-path",
            "--export-area-page",
            f"--export-filename={tmp_path}",
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=60,
        )

        if result.returncode != 0:
            print(
                f"  ❌ Inkscape selhal pro '{svg_file.name}': {result.stderr.strip()}"
            )
            return False

        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            print(f"  ❌ Inkscape nevytvořil výstupní soubor pro '{svg_file.name}'.")
            return False

        # Overwrite original with the converted file
        shutil.move(str(tmp_path), str(svg_file))
        return True

    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def run(output_dir: Path) -> List[Path]:
    """
    Process all SVG files in output/ directory and convert all text to vector paths.
    """
    print(f"\n🖋️  [Krok 2] Převod textu na křivky (Inkscape) v: {output_dir}...")
    inkscape_bin = shutil.which("inkscape")
    if not inkscape_bin:
        raise RuntimeError("Inkscape nebyl nalezen v PATH. Nainstalujte inkscape.")

    svg_files = sorted(output_dir.glob("*.svg"))
    if not svg_files:
        print(f"  ℹ️  V '{output_dir}' nebyly nalezeny žádné SVG soubory.")
        return []

    successful: List[Path] = []
    for svg_file in svg_files:
        print(f"  Converting text: {svg_file.name}...")
        if convert_text_to_path(svg_file, inkscape_bin):
            print(f"  ✅ Text převeden na křivky: {svg_file.name}")
            successful.append(svg_file)
        else:
            print(f"  ⚠️  Chyba při převodu textu v: {svg_file.name}")

    return successful


if __name__ == "__main__":
    base_path = Path(__file__).resolve().parent.parent
    run(base_path / "output")
