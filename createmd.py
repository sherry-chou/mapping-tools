"""
createmd.py

Author:
    Sherry Chou

Purpose:
    Converts a document (PDF, PPTX, DOCX, etc.) to Markdown using Docling (https://docling.ai/#quickstart) and saves it to a file.

Parameters:
    input_file (required)  : Path to the input file (relative or absolute)
    -o, --output (optional): Output Markdown file path
                             (default: same folder and base name as the input, with a .md extension)

Usage:
    # Convert report.pdf; saves report.md in the same folder
    python createmd.py report.pdf

    # Convert report.pdf and save as hello.md
    python createmd.py report.pdf -o hello.md

    # Convert a PowerPoint file
    python createmd.py hello.pptx

    # Convert a file in another folder with a custom output path
    python createmd.py /data/studies/report.pdf -o /data/out/report.md

Notes:
    - Needs Python 3.10+ interpreter.
        - If uv is available or can be installed, run uv venv --python 3.12 .venv and then uv pip install docling.
        - See https://docs.astral.sh/uv/pip/environments/ for more details.
    - Missing output folders are created automatically.
    - Use -h or --help to show the built-in argument help.
"""

import argparse
from pathlib import Path

from docling.document_converter import DocumentConverter

# Parse the input file and optional output location from the command line
parser = argparse.ArgumentParser(
    description="Convert a document (PDF, PPTX, DOCX, etc.) to Markdown with Docling"
)
parser.add_argument(
    "input_file", type=str, help="Path to the input file (e.g., report.pdf, hello.pptx)"
)
parser.add_argument(
    "-o",
    "--output",
    type=str,
    default=None,
    help="Output Markdown file path (default: input file name with .md, "
    "in the same directory as the input)",
)
args = parser.parse_args()

input_path = Path(args.input_file).expanduser()

# Default output: same folder and base name as the input, with a .md extension
if args.output:
    output_path = Path(args.output).expanduser()
else:
    output_path = input_path.with_suffix(".md")

converter = DocumentConverter()
result = converter.convert(str(input_path))

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(result.document.export_to_markdown(), encoding="utf-8")

print(f"Markdown saved to: {output_path}")
