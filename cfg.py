"""Configuration file for branding asset generation pipeline."""

from typing import Dict, Tuple

# Mapping of SVG filenames to target raster resolutions (width, height in pixels).
RESOLUTIONS: Dict[str, Tuple[int, int]] = {
    "sotial_logo.svg": (3840, 3840),
    "logo.svg": (3840, 3840),
    "text.svg": (2560, 1440),
}

DEFAULT_BASE_WIDTH: int = 2560
DEFAULT_RESOLUTION: Tuple[int, int] = (2560, 1440)

# Konfigurace pro WebP optimalizaci
WEBP_QUALITY: int = 90  # Kvalita komprese (1-100)
WEBP_LOSSLESS: bool = False  # True pro bezztrátovou kompresi (ideální u vektorů/ikon)
