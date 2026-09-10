"""
src/sovereign/lineage/injectors/ooxml.py
Pure Standard-Library Open Packaging Conventions (OPC) Metadata Injector
Works universally across .docx, .xlsx, and .pptx without third-party dependencies.
"""
import io
import xml.etree.ElementTree as ET
import zipfile
from typing import Dict

CUSTOM_PROPS_PART = "docProps/custom.xml"
CONTENT_TYPES_PART = "[Content_Types].xml"
RELS_PART = "_rels/.rels"

CUSTOM_PROPS_NS = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
VTYPES_NS = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
REL_TYPE_CUSTOM_PROPS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/custom-properties"
CONTENT_TYPE_CUSTOM_PROPS = "application/vnd.openxmlformats-officedocument.custom-properties+xml"


def inject_ooxml_lineage(file_bytes: bytes, lineage_properties: Dict[str, str]) -> bytes:
    """
    Directly injects sovereign lineage properties into an OOXML zip archive (.docx, .xlsx, .pptx).
    """
    in_mem_in = io.BytesIO(file_bytes)
    in_mem_out = io.BytesIO()

    with zipfile.ZipFile(in_mem_in, "r") as src, zipfile.ZipFile(in_mem_out, "w", zipfile.ZIP_DEFLATED) as dst:
        # 1. Build docProps/custom.xml
        root = ET.Element(f"{{{CUSTOM_PROPS_NS}}}Properties")
        root.set("xmlns:vt", VTYPES_NS)

        pid = 2
        for name, value in lineage_properties.items():
            prop = ET.SubElement(root, f"{{{CUSTOM_PROPS_NS}}}property")
            prop.set("fmtid", "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}")
            prop.set("pid", str(pid))
            prop.set("name", str(name))
            lpwstr = ET.SubElement(prop, f"{{{VTYPES_NS}}}lpwstr")
            lpwstr.text = str(value)
            pid += 1

        custom_xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)

        # 2. Iterate existing archive parts and inject relations/overrides
        has_custom_prop_content_type = False
        has_custom_prop_rel = False

        for item in src.infolist():
            content = src.read(item.filename)

            if item.filename == CONTENT_TYPES_PART:
                content_str = content.decode("utf-8", errors="ignore")
                if CONTENT_TYPE_CUSTOM_PROPS in content_str or CUSTOM_PROPS_PART in content_str:
                    has_custom_prop_content_type = True
                else:
                    insert_point = content_str.rfind("</Types>")
                    if insert_point != -1:
                        override_elem = f'  <Override PartName="/{CUSTOM_PROPS_PART}" ContentType="{CONTENT_TYPE_CUSTOM_PROPS}"/>\n'
                        content_str = content_str[:insert_point] + override_elem + content_str[insert_point:]
                        content = content_str.encode("utf-8")
                        has_custom_prop_content_type = True

            elif item.filename == RELS_PART:
                rels_str = content.decode("utf-8", errors="ignore")
                if REL_TYPE_CUSTOM_PROPS in rels_str or CUSTOM_PROPS_PART in rels_str:
                    has_custom_prop_rel = True
                else:
                    insert_point = rels_str.rfind("</Relationships>")
                    if insert_point != -1:
                        rel_elem = f'  <Relationship Id="rIdSovereignCustomProps" Type="{REL_TYPE_CUSTOM_PROPS}" Target="{CUSTOM_PROPS_PART}"/>\n'
                        rels_str = rels_str[:insert_point] + rel_elem + rels_str[insert_point:]
                        content = rels_str.encode("utf-8")
                        has_custom_prop_rel = True

            elif item.filename.lower() == CUSTOM_PROPS_PART.lower():
                # Will be replaced with newly generated custom.xml
                continue

            dst.writestr(item, content)

        # 3. Write updated custom.xml
        dst.writestr(CUSTOM_PROPS_PART, custom_xml_bytes)

    return in_mem_out.getvalue()


def extract_ooxml_lineage(file_bytes: bytes) -> Dict[str, str]:
    """
    Extracts custom document properties from an OOXML zip archive.
    """
    in_mem = io.BytesIO(file_bytes)
    properties: Dict[str, str] = {}

    try:
        with zipfile.ZipFile(in_mem, "r") as zf:
            custom_part_name = None
            for name in zf.namelist():
                if name.lower() == CUSTOM_PROPS_PART.lower():
                    custom_part_name = name
                    break

            if not custom_part_name:
                return properties

            xml_bytes = zf.read(custom_part_name)
            root = ET.fromstring(xml_bytes)

            for elem in root:
                # Matches property tags regardless of namespace prefix
                tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag_name == "property":
                    prop_name = elem.attrib.get("name")
                    if prop_name:
                        # Value is in the first child tag text (e.g. vt:lpwstr) or element text
                        prop_value = ""
                        for child in elem:
                            if child.text:
                                prop_value = child.text
                                break
                        if not prop_value and elem.text and elem.text.strip():
                            prop_value = elem.text.strip()
                        properties[prop_name] = prop_value

    except Exception:
        return {}

    return properties
