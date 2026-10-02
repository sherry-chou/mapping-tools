"""
lblc_unitconvert.py

Author:
    Sherry Chou

Purpose:
    Reads Table2_formatted.txt (from ama_table2_formatter.py) and writes
    AMA_Table2_full.xlsx with columns:
        Analyte | Specimen | Conventional Unit | Conversion Factor | SI Unit

    Each input line is one record, e.g.,
        Glucose Serum mg/dL 0.0555 mmol/L

Usage:
    python lblc_unitconvert.py  # Table2_formatted.txt as default input, stored in same path as this program
    python lblc_unitconvert.py path\\to\\Table2_formatted.txt
"""

# Source: https://academic.oup.com/amamanualofstyle/si-conversion-calculator (Table 2)
import re
import sys
from pathlib import Path

import pandas as pd

INPUT_FILE = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else Path(__file__).with_name("Table2_formatted.txt")
)
if not INPUT_FILE.exists():
    sys.exit(f"Input file not found: {INPUT_FILE}")
OUTPUT_FILE = INPUT_FILE.with_name("AMA_Table2_full.xlsx")

HEADER = "Analyte Specimen Conventional unit Conversion factor SI unit"

# Specimens used in AMA Table 2 (longest first so "Serum, plasma" wins over "Serum")
SPECIMENS = [
    "Serum, whole blood",
    "Serum, plasma",
    "Serum, Plasma",
    "Arterial blood",
    "Red blood cells",
    "Whole blood",
    "Serum",
    "Plasma",
    "Urine",
    "Stool",
]
SPEC_RE = "|".join(re.escape(s) for s in SPECIMENS)
NUM = r"[<>]?\d+(?:\.\d+)?"

# analyte  specimen  [conventional unit]  factor  [SI unit]
ROW_RE = re.compile(
    rf"^(?P<analyte>.+?) (?P<spec>{SPEC_RE})"
    rf"(?: (?P<conv>.+?))? (?P<factor>{NUM})(?: (?P<si>.+))?$"
)
# Fallback for rows without specimen (e.g. Nitroprusside)
NOSPEC_RE = re.compile(
    rf"^(?P<analyte>.+?) (?P<conv>\S+) (?P<factor>{NUM})(?: (?P<si>.+))?$"
)


def clean(t):
    t = t.replace("\xa0", " ").replace("\u2009", " ").replace("\u00b5", "\u03bc")
    return re.sub(r"\s+", " ", t).strip()


records, unparsed = [], []
for line in INPUT_FILE.read_text(encoding="utf-8-sig").splitlines():
    line = clean(line)
    if not line or line == HEADER:
        continue
    m = ROW_RE.match(line) or NOSPEC_RE.match(line)
    if not m:
        unparsed.append(line)
        continue
    g = m.groupdict()
    records.append(
        [
            g["analyte"].strip(", "),
            (g.get("spec") or "").strip(),
            (g.get("conv") or "").strip(),
            g["factor"],
            (g.get("si") or "").strip(),
        ]
    )

cols = ["Analyte", "Specimen", "Conventional Unit", "Conversion Factor", "SI Unit"]
df = pd.DataFrame(records, columns=cols)
df = df.drop_duplicates().sort_values(by=["Analyte", "Specimen"]).reset_index(drop=True)

df.to_excel(OUTPUT_FILE, index=False)
print("Reading:", INPUT_FILE)
print("Rows parsed:", len(df))
print("Saved:", OUTPUT_FILE)
if unparsed:
    print(f"\nWARNING - {len(unparsed)} line(s) could not be parsed:")
    for u in unparsed:
        print("  ", u)
