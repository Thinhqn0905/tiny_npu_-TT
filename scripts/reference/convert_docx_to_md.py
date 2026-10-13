#!/usr/bin/env python3
"""
Convert all .docx specification documents in Tiny_NPU to clean Markdown (.md).
Extracts AGENTS.docx content to generate the project's CLAUDE.md.
Deletes all .docx files once Markdown files are successfully generated.
Uses standard Python library (zipfile, xml.etree.ElementTree) with zero third-party dependencies.
"""

import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

# Namespaces for WordprocessingML
NS = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
    'v': 'urn:schemas-microsoft-com:vml',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'w14': 'http://schemas.microsoft.com/office/word/2010/wordml',
}

def get_text_from_node(node):
    """Recursively extract all text inside a node."""
    texts = []
    for elem in node.iter():
        if elem.tag.endswith('}t'):
            if elem.text:
                texts.append(elem.text)
        elif elem.tag.endswith('}tab'):
            texts.append('\t')
        elif elem.tag.endswith('}br'):
            texts.append('\n')
    return "".join(texts)

def parse_docx_to_markdown(docx_path: Path) -> str:
    """Parse word/document.xml from a .docx file and convert to Markdown."""
    if not zipfile.is_zipfile(docx_path):
        return f"# Error: {docx_path.name} is not a valid zip/docx file."

    with zipfile.ZipFile(docx_path, 'r') as zf:
        if 'word/document.xml' not in zf.namelist():
            return f"# Error: word/document.xml not found in {docx_path.name}"
        xml_content = zf.read('word/document.xml')

    root = ET.fromstring(xml_content)
    body = root.find('w:body', NS)
    if body is None:
        return ""

    md_lines = []

    for child in body:
        tag = child.tag.split('}')[-1]

        if tag == 'p': # Paragraph
            pPr = child.find('w:pPr', NS)
            pStyle = None
            is_bullet = False
            is_num = False
            num_ilvl = 0

            if pPr is not None:
                style_elem = pPr.find('w:pStyle', NS)
                if style_elem is not None:
                    pStyle = style_elem.attrib.get(f'{{{NS["w"]}}}val', '')

                numPr = pPr.find('w:numPr', NS)
                if numPr is not None:
                    ilvl_elem = numPr.find('w:ilvl', NS)
                    if ilvl_elem is not None:
                        try:
                            num_ilvl = int(ilvl_elem.attrib.get(f'{{{NS["w"]}}}val', '0'))
                        except ValueError:
                            num_ilvl = 0
                    is_bullet = True

            # Process runs in paragraph
            run_pieces = []
            for r in child.findall('w:r', NS):
                rPr = r.find('w:rPr', NS)
                b = rPr.find('w:b', NS) is not None if rPr is not None else False
                i = rPr.find('w:i', NS) is not None if rPr is not None else False
                code_font = False
                if rPr is not None:
                    rFonts = rPr.find('w:rFonts', NS)
                    if rFonts is not None:
                        ascii_font = rFonts.attrib.get(f'{{{NS["w"]}}}ascii', '')
                        if any(f in ascii_font for f in ['Courier', 'Consolas', 'Mono', 'Lucida Console']):
                            code_font = True

                t_text = get_text_from_node(r)
                if not t_text:
                    continue

                formatted_text = t_text
                if code_font and len(formatted_text.strip()) > 0:
                    formatted_text = f"`{formatted_text}`"
                if b and len(formatted_text.strip()) > 0:
                    formatted_text = f"**{formatted_text}**"
                if i and len(formatted_text.strip()) > 0:
                    formatted_text = f"*{formatted_text}*"

                run_pieces.append(formatted_text)

            p_text = "".join(run_pieces).strip()
            if not p_text:
                md_lines.append("")
                continue

            # Check heading style
            if pStyle:
                style_lower = pStyle.lower()
                if 'heading 1' in style_lower or pStyle == '1' or style_lower == 'heading1':
                    md_lines.append(f"\n# {p_text}\n")
                elif 'heading 2' in style_lower or pStyle == '2' or style_lower == 'heading2':
                    md_lines.append(f"\n## {p_text}\n")
                elif 'heading 3' in style_lower or pStyle == '3' or style_lower == 'heading3':
                    md_lines.append(f"\n### {p_text}\n")
                elif 'heading 4' in style_lower or pStyle == '4' or style_lower == 'heading4':
                    md_lines.append(f"\n#### {p_text}\n")
                elif 'title' in style_lower:
                    md_lines.append(f"\n# {p_text}\n")
                elif 'subtitle' in style_lower:
                    md_lines.append(f"\n*{p_text}*\n")
                elif is_bullet:
                    indent = "  " * num_ilvl
                    md_lines.append(f"{indent}- {p_text}")
                else:
                    md_lines.append(p_text)
            elif is_bullet:
                indent = "  " * num_ilvl
                md_lines.append(f"{indent}- {p_text}")
            else:
                md_lines.append(p_text)

        elif tag == 'tbl': # Table
            rows = []
            for tr in child.findall('w:tr', NS):
                row_cells = []
                for tc in tr.findall('w:tc', NS):
                    cell_text_parts = []
                    for p in tc.findall('w:p', NS):
                        p_t = get_text_from_node(p).strip()
                        if p_t:
                            cell_text_parts.append(p_t)
                    cell_str = " ".join(cell_text_parts).replace('\n', ' ').replace('|', '\\|')
                    row_cells.append(cell_str)
                if row_cells:
                    rows.append(row_cells)

            if rows:
                max_cols = max(len(r) for r in rows)
                norm_rows = [r + [""] * (max_cols - len(r)) for r in rows]

                header = norm_rows[0]
                md_lines.append("")
                md_lines.append("| " + " | ".join(header) + " |")
                md_lines.append("| " + " | ".join(["---"] * max_cols) + " |")
                for r in norm_rows[1:]:
                    md_lines.append("| " + " | ".join(r) + " |")
                md_lines.append("")

    return "\n".join(md_lines)

def build_claude_md(agents_md_content: str, project_root: Path) -> str:
    """Build CLAUDE.md incorporating AGENTS.md rules and project guidelines."""
    claude_md = f"""# CLAUDE.md - TinyML NPU ASIC Guidelines & Agent Protocols

## Project Overview
- **Project Name:** Scalable TinyML Neural Processing Unit (NPU) for Arrhythmia ECG Detection
- **Target Platform:** Tiny Tapeout Shuttle (IHP SG13G2 130nm / SkyWater Sky130A / GF180MCU)
- **Tile Architecture:** Parameterized systolic array scalable from 1x1 Tile (884 cells) up to MxN grids (2x2 evaluated).
- **Clock / Operating Specs:** 50 MHz nominal clock, 1.8V / 1.2V core, synchronous active-low reset (`rst_n`).

---

## Agent Guidelines & Protocols (from AGENTS.docx)

{agents_md_content}

---

## Hardware Design & Tapeout Constraints
1. **Clock & Reset:**
   - Single synchronous clock domain (`clk`), nominal 50 MHz.
   - Synchronous or active-low asynchronous reset (`rst_n`), fully synchronized internally.
   - Zero latches, zero combinational loops, no derived clocks or gate delays.

2. **Pin Mapping (Tiny Tapeout Standard):**
   - `ui_in[7:0]`: Dedicated inputs (activation / weight stream).
   - `uo_out[7:0]`: Dedicated outputs (quantized output / status flags / argmax index).
   - `uio_in[7:0]`: Bidirectional input (command opcode, shift value, mode control).
   - `uio_out[7:0]`: Bidirectional output (accumulators, telemetry, overflow).
   - `uio_oe[7:0]`: Bidirectional output enable bus.
   - `ena`: Chip enable (active-high).

3. **Multi-Scale Systolic Array Rules:**
   - Datapath parameters: `DATA_WIDTH = 8` (signed int8), `ACC_WIDTH = 24` (signed int24).
   - Horizontal systolic activation forwarding (`data_a_out`).
   - Vertical systolic weight forwarding (`data_b_out`).
   - Vertical accumulator cascade bus (`cascade_acc_in`).
   - Bit-exact requantization: `(Acc + round_offset) >>> shift` with saturated clipping.

4. **Verification Evidence & Sign-Off Contract:**
   - All RTL additions must maintain traceability to `schemas/rtm.json` requirements.
   - Standalone simulation via Icarus Verilog (`iverilog`) or Cocotb testbenches.
   - 100% line, branch, and toggle coverage on datapath blocks.
   - Synthesis check with zero timing violations at 50 MHz.
"""
    return claude_md

def main():
    project_root = Path(r"E:\PROJECTS\tinyml_npu_ecg")
    base_dir = project_root / "Tiny_NPU"
    if not base_dir.exists():
        print(f"Error: {base_dir} does not exist")
        sys.exit(1)

    docx_files = list(base_dir.rglob("*.docx"))
    print(f"Found {len(docx_files)} .docx files in {base_dir}")

    converted_files = []
    agents_md_content = ""

    for docx_path in docx_files:
        md_path = docx_path.with_suffix('.md')
        print(f"Converting: {docx_path.relative_to(base_dir)} -> {md_path.name}")
        md_content = parse_docx_to_markdown(docx_path)
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        converted_files.append((docx_path, md_path))

        if docx_path.name.lower() == "agents.docx":
            agents_md_content = md_content

    print(f"\nSuccessfully converted {len(converted_files)} files to Markdown (.md)!")

    # Generate CLAUDE.md
    claude_md_path = project_root / "CLAUDE.md"
    print(f"\nGenerating {claude_md_path} from AGENTS.md...")
    claude_md_text = build_claude_md(agents_md_content, project_root)
    with open(claude_md_path, 'w', encoding='utf-8') as f:
        f.write(claude_md_text)
    print("CLAUDE.md successfully created!")

    # Verify all .md files exist and have content before deleting .docx
    all_valid = True
    for docx_path, md_path in converted_files:
        if not md_path.exists() or md_path.stat().st_size == 0:
            print(f"Error: {md_path} is empty or missing. Aborting deletion!")
            all_valid = False
            break

    if all_valid:
        print("\nAll Markdown files validated. Proceeding to delete all .docx files...")
        deleted_count = 0
        for docx_path, _ in converted_files:
            try:
                docx_path.unlink()
                deleted_count += 1
            except Exception as e:
                print(f"Warning: Could not delete {docx_path}: {e}")
        print(f"Successfully deleted {deleted_count} .docx files!")

if __name__ == '__main__':
    main()
