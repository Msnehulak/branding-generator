"""Step 1: In-line embedding of externally linked elements in SVG files."""

import base64
import mimetypes
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
SODIPODI_NS = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"

COMMON_NAMESPACES = {
    "": SVG_NS,
    "svg": SVG_NS,
    "xlink": XLINK_NS,
    "inkscape": INKSCAPE_NS,
    "sodipodi": SODIPODI_NS,
}


def register_svg_namespaces(file_paths: List[Path]) -> None:
    """Extract and register all XML namespaces across given SVG files."""
    registered: Dict[str, str] = dict(COMMON_NAMESPACES)

    for path in file_paths:
        if not path.is_file():
            continue
        try:
            for _, node in ET.iterparse(str(path), events=["start-ns"]):
                prefix, uri = node
                if prefix not in registered:
                    registered[prefix] = uri
        except Exception:
            pass

    for prefix, uri in registered.items():
        ET.register_namespace(prefix, uri)


def resolve_linked_path(href: str, source_svg: Path, base_dir: Path) -> Optional[Path]:
    """
    Resolve a linked file path relative to the source SVG, project root,
    or common asset directories like 'base/' or 'presets/'.
    """
    # Clean fragment identifier if present (e.g. file.svg#layer1)
    clean_href = href.split("#")[0]
    if not clean_href:
        return None

    candidates = [
        source_svg.parent / clean_href,
        base_dir / clean_href,
        base_dir / "base" / clean_href,
        base_dir / "presets" / clean_href,
    ]

    for candidate in candidates:
        candidate_resolved = candidate.resolve()
        if candidate_resolved.is_file():
            return candidate_resolved

    return None


def get_href(elem: ET.Element) -> Optional[str]:
    """Retrieve href attribute considering both SVG 2 and XLink namespaces."""
    return elem.get(f"{{{XLINK_NS}}}href") or elem.get("href")


def set_href(elem: ET.Element, href_value: str) -> None:
    """Set href attribute updating both SVG 2 and XLink namespaces."""
    if f"{{{XLINK_NS}}}href" in elem.attrib or elem.get(f"{{{XLINK_NS}}}href") is not None:
        elem.set(f"{{{XLINK_NS}}}href", href_value)
    elem.set("href", href_value)


def prefix_ids_in_tree(tree_root: ET.Element, prefix: str) -> None:
    """
    Rename all element IDs with a unique prefix and update references
    (url(#id) and xlink:href="#id") to prevent namespace/ID clashes.
    """
    id_map: Dict[str, str] = {}
    for elem in tree_root.iter():
        elem_id = elem.get("id")
        if elem_id:
            new_id = f"{prefix}_{elem_id}"
            id_map[elem_id] = new_id
            elem.set("id", new_id)

    if not id_map:
        return

    # Update references in all elements
    url_pattern = re.compile(r"url\(#([^)]+)\)")

    for elem in tree_root.iter():
        # Update hrefs (e.g., in <use> or <textPath>)
        href = get_href(elem)
        if href and href.startswith("#"):
            old_ref = href[1:]
            if old_ref in id_map:
                set_href(elem, f"#{id_map[old_ref]}")

        # Update attributes with url(#id) or style properties
        for attr_name, attr_val in list(elem.attrib.items()):
            if attr_name in ("href", f"{{{XLINK_NS}}}href", "id"):
                continue

            # Check style and presentation attributes (fill, stroke, clip-path, filter, mask)
            if "url(#" in attr_val:
                def replace_url(match: re.Match) -> str:
                    ref_id = match.group(1)
                    return f"url(#{id_map.get(ref_id, ref_id)})"

                new_val = url_pattern.sub(replace_url, attr_val)
                elem.set(attr_name, new_val)


def clean_unit(val: Optional[str]) -> str:
    """Strip CSS / SVG units (mm, cm, px, pt) and return raw value or 100%."""
    if not val:
        return "100%"
    return re.sub(r"[a-zA-Z%]+$", "", val.strip())


def embed_image_svg(image_elem: ET.Element, linked_svg_path: Path, embed_idx: int) -> ET.Element:
    """
    Convert an <image> element linking to an external SVG into a standalone
    nested <svg> element containing all elements from the target SVG.
    """
    sub_tree = ET.parse(str(linked_svg_path))
    sub_root = sub_tree.getroot()

    # Prefix IDs to avoid collisions
    prefix_ids_in_tree(sub_root, f"emb{embed_idx}")

    # Create nested <svg> element
    new_svg = ET.Element(f"{{{SVG_NS}}}svg")

    # Inherit positioning & sizing from original <image> element
    for attr in [
        "x", "y", "width", "height", "transform", "style",
        "id", "preserveAspectRatio", "clip-path", "mask", "opacity"
    ]:
        val = image_elem.get(attr)
        if val is not None:
            new_svg.set(attr, val)

    # Transfer viewBox from linked SVG or generate from width/height
    vb = sub_root.get("viewBox")
    if vb:
        new_svg.set("viewBox", vb)
    else:
        w = clean_unit(sub_root.get("width"))
        h = clean_unit(sub_root.get("height"))
        new_svg.set("viewBox", f"0 0 {w} {h}")

    # Transfer all child elements of linked SVG root into nested <svg>
    for child in list(sub_root):
        new_svg.append(child)

    return new_svg


def embed_raster_image(image_elem: ET.Element, raster_path: Path) -> None:
    """Embed a raster image file (PNG, JPG, etc.) as a base64 Data URI."""
    mime, _ = mimetypes.guess_type(str(raster_path))
    if not mime:
        mime = "image/png"

    with open(raster_path, "rb") as img_file:
        b64_content = base64.b64encode(img_file.read()).decode("ascii")

    data_uri = f"data:{mime};base64,{b64_content}"
    set_href(image_elem, data_uri)


def process_single_svg(svg_path: Path, output_path: Path, base_dir: Path) -> int:
    """
    Process an SVG file, embedding all external links (<image>, <use>),
    and saving the standalone SVG to output_path.
    Returns the count of embedded external assets.
    """
    tree = ET.parse(str(svg_path))
    root = tree.getroot()

    # Build parent mapping to allow element replacement
    parent_map = {child: parent for parent in root.iter() for child in parent}

    embedded_count = 0

    # 1. Process <image> elements
    for image_elem in list(root.iter(f"{{{SVG_NS}}}image")) + list(root.iter("image")):
        href = get_href(image_elem)
        if not href or href.startswith("#") or href.startswith("data:"):
            continue

        target_file = resolve_linked_path(href, svg_path, base_dir)
        if not target_file:
            print(f"  ⚠️  Soubor '{href}' odkazovaný z '{svg_path.name}' nebyl nalezen.")
            continue

        embedded_count += 1
        ext = target_file.suffix.lower()

        if ext == ".svg":
            # Embed vector SVG as nested <svg>
            parent = parent_map.get(image_elem)
            if parent is not None:
                new_svg = embed_image_svg(image_elem, target_file, embedded_count)
                idx = list(parent).index(image_elem)
                parent.remove(image_elem)
                parent.insert(idx, new_svg)
                # Update parent map for new element
                parent_map[new_svg] = parent
                for c in new_svg.iter():
                    for ch in c:
                        parent_map[ch] = c
                print(f"  🔗 In-line SVG embedováno: {target_file.name} -> <svg>")
        else:
            # Embed raster image as base64 Data URI
            embed_raster_image(image_elem, target_file)
            print(f"  🖼️  Rastrový obrázek převeden na data URI: {target_file.name}")

    # 2. Process external <use> elements
    for use_elem in list(root.iter(f"{{{SVG_NS}}}use")) + list(root.iter("use")):
        href = get_href(use_elem)
        if not href or href.startswith("#") or href.startswith("data:"):
            continue

        parts = href.split("#", 1)
        file_part = parts[0]
        frag_id = parts[1] if len(parts) > 1 else None

        target_file = resolve_linked_path(file_part, svg_path, base_dir)
        if not target_file or target_file.suffix.lower() != ".svg":
            continue

        embedded_count += 1
        sub_tree = ET.parse(str(target_file))
        sub_root = sub_tree.getroot()
        prefix = f"emb_use_{embedded_count}"
        prefix_ids_in_tree(sub_root, prefix)

        # Ensure root has <defs>
        defs_elem = root.find(f"{{{SVG_NS}}}defs")
        if defs_elem is None:
            defs_elem = root.find("defs")
        if defs_elem is None:
            defs_elem = ET.Element(f"{{{SVG_NS}}}defs")
            root.insert(0, defs_elem)

        if frag_id:
            target_id = f"{prefix}_{frag_id}"
            found_elem = None
            for e in sub_root.iter():
                if e.get("id") == target_id:
                    found_elem = e
                    break
            if found_elem is not None:
                defs_elem.append(found_elem)
                set_href(use_elem, f"#{target_id}")
                print(f"  🔗 Vložen externí symbol z {target_file.name}#{frag_id} do <defs>")
        else:
            # Embed the whole SVG body as a group
            container_g = ET.Element(f"{{{SVG_NS}}}g", {"id": f"{prefix}_container"})
            for child in list(sub_root):
                container_g.append(child)
            defs_elem.append(container_g)
            set_href(use_elem, f"#{prefix}_container")
            print(f"  🔗 Vložen celý externí SVG {target_file.name} do <defs>")

    # Ensure output directory exists and write standalone SVG
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(output_path), encoding="utf-8", xml_declaration=True)
    return embedded_count


def run(presets_dir: Path, output_dir: Path, base_dir: Path) -> List[Path]:
    """
    Search presets/ folder, embed external resources for all SVG files,
    and write standalone SVGs into output/.
    """
    print(f"\n📦 [Krok 1] Prohledávám složku předvoleb: {presets_dir}...")
    output_dir.mkdir(parents=True, exist_ok=True)

    svg_files = sorted(presets_dir.glob("*.svg"))
    if not svg_files:
        print(f"  ℹ️  V '{presets_dir}' nebyly nalezeny žádné SVG soubory.")
        return []

    # Register all namespaces beforehand
    all_svgs = list(svg_files)
    if (base_dir / "base").exists():
        all_svgs.extend((base_dir / "base").glob("*.svg"))
    register_svg_namespaces(all_svgs)

    processed_files: List[Path] = []
    for svg_file in svg_files:
        target_output = output_dir / svg_file.name
        print(f"  📄 Zpracovávám: {svg_file.name} -> {target_output.name}")
        embedded_count = process_single_svg(svg_file, target_output, base_dir)
        print(f"  ✨ Dokončeno '{svg_file.name}' (sloučeno {embedded_count} externích prvků)")
        processed_files.append(target_output)

    return processed_files


if __name__ == "__main__":
    base_path = Path(__file__).resolve().parent.parent
    run(base_path / "presets", base_path / "output", base_path)
