"""Branding Assets Generation Pipeline (Krok 0 až Krok 4)."""

import argparse
import shutil
import sys
import time
from pathlib import Path
from typing import Optional

from scripts import check_deps, convert_text, embed_svg, optimize_svg, rasterize


class BrandingPipeline:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = (base_dir or Path(__file__).resolve().parent.parent).resolve()
        self.font_dir = self.base_dir / "font"
        self.presets_dir = self.base_dir / "presets"
        self.output_dir = self.base_dir / "output"
        self.svg_dir = self.output_dir / "svg"
        self.png_dir = self.output_dir / "png"
        self.webp_dir = self.output_dir / "webp"
        self.cfg_file = self.base_dir / "cfg.py"

    def clean_output(self) -> None:
        """Smaže veškeré předchozí výstupy ve složce output/."""
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            print(f"🧹 Složka '{self.output_dir.name}/' byla kompletně vyčištěna.")

    def run_step0(self) -> None:
        """Krok 0: Kontrola závislostí a instalace fontů."""
        check_deps.run(self.font_dir)

    def run_step1(self) -> list:
        """Krok 1: Embedování propojených prvků z presets/ do output/svg/."""
        return embed_svg.run(self.presets_dir, self.svg_dir, self.base_dir)

    def run_step2(self) -> list:
        """Krok 2: Inkscape – Převod textu na křivky v output/svg/."""
        return convert_text.run(self.svg_dir)

    def run_step3(self) -> list:
        """Krok 3: SVGO – Optimalizace SVG v output/svg/."""
        return optimize_svg.run(self.svg_dir)

    def run_step4(self) -> dict:
        """Krok 4: Rasterizace do PNG a optimalizovaného WebP."""
        return rasterize.run(self.svg_dir, self.png_dir, self.webp_dir, self.cfg_file)

    def run_all(self, skip_steps: Optional[set] = None) -> bool:
        """Spustí celou pipeline sekvenčně."""
        skip = skip_steps or set()
        start_time = time.time()

        print("=" * 65)
        print("🚀 SPUŠTĚNÍ AUTOMATIZOVANÉ BRANDING ASSETS PIPELINE")
        print("=" * 65)

        try:
            if 0 not in skip:
                self.run_step0()

            if 1 not in skip:
                self.run_step1()

            if 2 not in skip:
                self.run_step2()

            if 3 not in skip:
                self.run_step3()

            if 4 not in skip:
                self.run_step4()

            elapsed = time.time() - start_time
            print("\n" + "=" * 65)
            print(f"🎉 PIPELINE ÚSPĚŠNĚ DOKONČENA za {elapsed:.2f} s")
            print("=" * 65)

            # Přehled vygenerovaných souborů podle podsložek
            if self.output_dir.exists():
                print(f"\n📂 Výstupy ve složce '{self.output_dir.name}/':")
                for subfolder in [self.svg_dir, self.png_dir, self.webp_dir]:
                    if subfolder.exists():
                        files = sorted(subfolder.glob("*.*"))
                        if files:
                            print(f"\n  📁 {subfolder.name}/")
                            for f in files:
                                size_kb = f.stat().st_size / 1024
                                print(f"    • {f.name:<25} ({size_kb:>7.1f} KiB)")
            print()
            return True

        except check_deps.DependencyError as e:
            print(f"\n{e}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"\n❌ Neočekávaná chyba v pipeline: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Automatizovaná pipeline pro generování branding assetů."
    )
    parser.add_argument(
        "--clean", action="store_true", help="Před spuštěním promazat složku output/"
    )
    parser.add_argument(
        "--skip-step0",
        action="store_true",
        help="Přeskočit krok 0 (kontrola závislostí a fonty)",
    )
    parser.add_argument(
        "--skip-step1", action="store_true", help="Přeskočit krok 1 (embedování)"
    )
    parser.add_argument(
        "--skip-step2", action="store_true", help="Přeskočit krok 2 (text na křivky)"
    )
    parser.add_argument(
        "--skip-step3", action="store_true", help="Přeskočit krok 3 (SVGO optimalizace)"
    )
    parser.add_argument(
        "--skip-step4",
        action="store_true",
        help="Přeskočit krok 4 (rasterizace PNG & WebP)",
    )
    parser.add_argument(
        "--step", type=int, choices=[0, 1, 2, 3, 4], help="Spustit pouze vybraný krok"
    )

    args = parser.parse_args()

    pipeline = BrandingPipeline()

    if args.clean:
        pipeline.clean_output()

    if args.step is not None:
        steps_to_skip = {0, 1, 2, 3, 4} - {args.step}
    else:
        steps_to_skip = set()
        if args.skip_step0:
            steps_to_skip.add(0)
        if args.skip_step1:
            steps_to_skip.add(1)
        if args.skip_step2:
            steps_to_skip.add(2)
        if args.skip_step3:
            steps_to_skip.add(3)
        if args.skip_step4:
            steps_to_skip.add(4)

    success = pipeline.run_all(skip_steps=steps_to_skip)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
