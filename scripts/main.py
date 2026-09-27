"""CLI entrypoint for running the pipeline from inside scripts directory."""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.pipeline import main

if __name__ == "__main__":
    main()
