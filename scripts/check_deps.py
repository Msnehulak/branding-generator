"""Step 0: Dependency verification and font registration."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class DependencyError(RuntimeError):
    """Raised when one or more required dependencies are missing."""
    pass


def get_command_version(cmd: List[str]) -> Tuple[bool, str]:
    """Run a version command and return (success, version_or_error_string)."""
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=15,
        )
        if result.returncode == 0:
            version_str = (result.stdout.strip() or result.stderr.strip()).splitlines()[0]
            return True, version_str
        return False, result.stderr.strip() or f"Exited with code {result.returncode}"
    except FileNotFoundError:
        return False, "Command not found in PATH"
    except Exception as e:
        return False, str(e)


def check_node() -> Tuple[bool, str]:
    """Verify Node.js is installed."""
    return get_command_version(["node", "--version"])


def check_inkscape() -> Tuple[bool, str]:
    """Verify Inkscape is installed."""
    return get_command_version(["inkscape", "--version"])


def check_svgo() -> Tuple[bool, str, List[str]]:
    """Verify SVGO is installed directly or via npx."""
    # Check if 'svgo' executable is available directly
    if shutil.which("svgo"):
        success, ver = get_command_version(["svgo", "--version"])
        if success:
            return True, ver, ["svgo"]

    # Check via npx
    if shutil.which("npx"):
        success, ver = get_command_version(["npx", "--yes", "svgo", "--version"])
        if success:
            return True, f"via npx: {ver}", ["npx", "--yes", "svgo"]

    return False, "Neither 'svgo' nor working 'npx svgo' found", []


def verify_dependencies() -> Dict[str, str]:
    """
    Check all required dependencies and return their versions.
    Raises DependencyError with clear remediation advice if any are missing.
    """
    print("\n🔍 [Krok 0] Kontrola systémových závislostí...")
    errors: List[str] = []
    versions: Dict[str, str] = {}

    # Check Node.js
    node_ok, node_ver = check_node()
    if node_ok:
        print(f"  ✅ Node.js:  {node_ver}")
        versions["node"] = node_ver
    else:
        print(f"  ❌ Node.js:  CHYBÍ ({node_ver})")
        errors.append(
            "- Node.js: Nainstalujte Node.js (např. 'sudo apt install nodejs npm' nebo přes nvm https://nodejs.org/)."
        )

    # Check Inkscape
    ink_ok, ink_ver = check_inkscape()
    if ink_ok:
        print(f"  ✅ Inkscape: {ink_ver}")
        versions["inkscape"] = ink_ver
    else:
        print(f"  ❌ Inkscape: CHYBÍ ({ink_ver})")
        errors.append(
            "- Inkscape: Nainstalujte Inkscape (např. 'sudo apt install inkscape' nebo 'pacman -S inkscape')."
        )

    # Check SVGO
    svgo_ok, svgo_ver, svgo_cmd = check_svgo()
    if svgo_ok:
        print(f"  ✅ SVGO:     {svgo_ver}")
        versions["svgo"] = svgo_ver
        versions["svgo_cmd"] = " ".join(svgo_cmd)
    else:
        print(f"  ❌ SVGO:     CHYBÍ ({svgo_ver})")
        errors.append(
            "- SVGO: Nainstalujte SVGO spuštěním 'npm install -g svgo' nebo ověřte dostupnost balíčku npm/npx."
        )

    # Check optional CairoSVG
    try:
        import cairosvg
        cairo_version = getattr(cairosvg, "__version__", "dostupné")
        print(f"  ✅ CairoSVG: {cairo_version} (Python)")
        versions["cairosvg"] = str(cairo_version)
    except ImportError:
        print("  ⚠️  CairoSVG: Není nainstalováno v Pythonu (pro PNG export bude použit fallback přes Inkscape).")

    if errors:
        msg = "\n❌ Chybí potřebné závislosti pro spuštění branding pipeline:\n" + "\n".join(errors)
        raise DependencyError(msg)

    return versions


def setup_fonts(font_dir: Path) -> List[str]:
    """
    Copy all font files (.ttf, .otf, etc.) from font_dir to ~/.local/share/fonts
    and refresh the system font cache using fc-cache -f.
    """
    print(f"\n🔤 [Krok 0] Načítání písem ze složky: {font_dir}...")

    if not font_dir.exists() or not font_dir.is_dir():
        print(f"  ⚠️  Složka s fonty '{font_dir}' neexistuje.")
        return []

    target_font_dir = Path.home() / ".local" / "share" / "fonts"
    target_font_dir.mkdir(parents=True, exist_ok=True)

    font_extensions = {".ttf", ".otf", ".woff", ".woff2", ".ttc"}
    installed_fonts: List[str] = []

    for file in font_dir.iterdir():
        if file.is_file() and file.suffix.lower() in font_extensions:
            dest = target_font_dir / file.name
            shutil.copy2(file, dest)
            installed_fonts.append(file.name)
            print(f"  📁 Zkopírován font: {file.name} -> {dest}")

    if not installed_fonts:
        print("  ℹ️  V zadané složce nebyly nalezeny žádné soubory písem.")
        return []

    # Refresh font cache
    fc_cache_bin = shutil.which("fc-cache")
    if fc_cache_bin:
        print("  🔄 Spouštím aktualizaci font cache ('fc-cache -f ~/.local/share/fonts/')...")
        res = subprocess.run(
            [fc_cache_bin, "-f", str(target_font_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            print(f"  ✅ Font cache úspěšně obnovena pro {len(installed_fonts)} písem.")
        else:
            print(f"  ⚠️  Varování při fc-cache: {res.stderr.strip()}")
    else:
        print("  ⚠️  'fc-cache' nebyl nalezen v PATH. Nainstalujte 'fontconfig'.")

    return installed_fonts


def run(font_dir: Path) -> Dict[str, str]:
    """Execute Step 0: check deps and set up fonts."""
    versions = verify_dependencies()
    setup_fonts(font_dir)
    return versions


if __name__ == "__main__":
    try:
        base_dir = Path(__file__).resolve().parent.parent
        run(base_dir / "font")
    except DependencyError as err:
        print(f"\n{err}", file=sys.stderr)
        sys.exit(1)
