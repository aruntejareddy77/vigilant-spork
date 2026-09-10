"""
src/sovereign/lineage/injectors/png.py
PNG tEXt Chunk Metadata Injector and Extractor using Pillow
"""
import io
from typing import Optional
from PIL import Image
from PIL.PngImagePlugin import PngInfo


def inject_png_lineage(image_bytes: bytes, lineage_summary: str) -> bytes:
    """
    Directly injects sovereign lineage metadata into a PNG tEXt chunk named 'sovereign_lineage'.
    """
    img = Image.open(io.BytesIO(image_bytes))
    png_info = PngInfo()

    # Preserve existing text keys if present
    if hasattr(img, "text") and isinstance(img.text, dict):
        for k, v in img.text.items():
            if k != "sovereign_lineage":
                png_info.add_text(k, str(v))

    png_info.add_text("sovereign_lineage", lineage_summary)

    out = io.BytesIO()
    img.save(out, format="PNG", pnginfo=png_info)
    return out.getvalue()


def extract_png_lineage(image_bytes: bytes) -> Optional[str]:
    """
    Extracts the 'sovereign_lineage' tEXt chunk from PNG image bytes.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if hasattr(img, "text") and isinstance(img.text, dict):
            return img.text.get("sovereign_lineage")
    except Exception:
        return None
    return None
