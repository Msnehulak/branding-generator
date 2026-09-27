"""Step 3: SVGO optimization for SVG files."""

import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple


def get_svgo_command() -> List[str]:
    """Determine the optimal command to invoke SVGO (local binary or npx)."""
    if shutil.which("svgo"):
        return ["svgo"]
    if shutil.which("npx"):
        return ["npx", "--yes", "svgo"]
    raise RuntimeError("SVGO není dostupné. Nainstalujte 'npm install -g svgo' nebo ověřte 'npx'.")


def optimize_svg_file(svg_file: Path, svgo_base_cmd: List[str]) -> Tuple[bool, int, int]:
    """
    Run SVGO on a single SVG file.
    Returns (success, initial_size, final_size).
    """
    initial_size = svg_file.stat().st_size
    cmd = svgo_base_cmd + [str(svg_file), "-o", str(svg_file)]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=60,
        )

        if result.returncode != 0:
            print(f"  ❌ SVGO selhal pro '{svg_file.name}': {result.stderr.strip()}")
            return False, initial_size, initial_size

        final_size = svg_file.stat().st_size
        return True, initial_size, final_size

    except Exception as e:
        print(f"  ❌ Chyba při spouštění SVGO na '{svg_file.name}': {e}")
        return False, initial_size, initial_size


def run(output_dir: Path) -> List[Path]:
    """
    Optimize all SVG files in output/ using SVGO.
    """
    print(f"\n⚡ [Krok 3] Optimalizace SVG (SVGO) v: {output_dir}...")
    svgo_cmd = get_svgo_command()
    print(f"  🔧 Použitý příkaz: {' '.join(svgo_cmd)}")

    svg_files = sorted(output_dir.glob("*.svg"))
    if not svg_files:
        print(f"  ℹ️  V '{output_dir}' nebyly nalezeny žádné SVG soubory.")
        return []

    optimized_files: List[Path] = []
    for svg_file in svg_files:
        success, size_before, size_after = optimize_svg_file(svg_file, svgo_cmd)
        if success:
            saved = size_before - size_after
            percent = (saved / size_before * 100) if size_before > 0 else 0
            print(
                f"  ✅ Optimalizováno: {svg_file.name} "
                f"({size_before / 1024:.1f} KiB -> {size_after / 1024:.1f} KiB, "
                f"úspora {percent:.1f}%)"
            )
            optimized_files.append(svg_file)
        else:
            print(f"  ⚠️  Optimalizace se nezdařila pro: {svg_file.name}")

    return optimized_files


if __name__ == "__main__":
    base_path = Path(__file__).resolve().parent.parent
    run(base_path / "output")
