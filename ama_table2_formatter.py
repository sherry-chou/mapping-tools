"""
ama_table2_formatter.py

Author:
    Sherry Chou

Purpose:
    Converts Table 2 text copied from the AMA "Units of measure converter" page
    into one row per line to be used for lblc_unitconvert.py. Format should be in:

    Analyte Specimen Conventional unit Conversion factor SI unit
    Glucose Serum mg/dL 0.0555 mmol/L

    The AMA copy puts each record on 3 lines:
    Analyte<TAB>Specimen<TAB>
        Conventional unit<TAB>Factor<TAB>
        SI unit

Usage:
    python ama_table2_formatter.py raw_table2.txt

Input:
    raw_table2.txt (directly just copy-pasted from the AMA "Units of measure converter" page and saved as txt file)

Output:
    Table2_formatted.txt
"""

import re
import sys

IN_FILE = sys.argv[1] if len(sys.argv) > 1 else "raw_table2.txt"
OUT_FILE = sys.argv[2] if len(sys.argv) > 2 else "Table2_formatted.txt"

HEADER = "Analyte Specimen Conventional unit Conversion factor SI unit"
NUM_RE = re.compile(r"^[<>]?\d+(?:\.\d+)?$")


def clean(t):
    t = (
        t.replace("\xa0", " ").replace("\u2009", " ").replace("\u00b5", "\u03bc")
    )  # micro sign -> Greek mu
    return re.sub(r"\s+", " ", t).strip()


def indent(line):
    return len(line) - len(line.lstrip(" "))


def cells(line):
    return [clean(c) for c in line.split("\t")]


def is_factor_line(line):
    """'  mg/dL<TAB>0.0555<TAB>' -> True"""
    if "\t" not in line:
        return False
    c = cells(line)
    return len(c) >= 2 and bool(NUM_RE.match(c[1]))


def is_analyte_line(line):
    """'Glucose<TAB>Serum<TAB>' -> True"""
    return (
        "\t" in line and not is_factor_line(line) and clean(line.split("\t")[0]) != ""
    )


def main():
    with open(IN_FILE, encoding="utf-8-sig") as f:
        lines = [l.rstrip("\r\n") for l in f]

    rows, headings = [], []  # headings = [(indent, text)]
    last_analyte = ""
    pending_heading_for_next = None  # e.g. 'Cholesterol' followed by 'Total'
    i, n = 0, len(lines)

    while i < n:
        line = lines[i]
        txt = clean(line)
        if not txt:
            i += 1
            continue
        low = txt.lower()

        # Table title / column header / "(see ...)" cross references
        if low.startswith(("table 2", "analyte specimen")) or "(see " in low:
            i += 1
            continue

        if is_analyte_line(line):
            ind = indent(line)
            c = cells(line)
            analyte, specimen = c[0], (c[1] if len(c) > 1 else "")

            # drop headings that are not parents of this row
            headings = [h for h in headings if h[0] < ind]

            if analyte.startswith("(") and last_analyte:  # '(Fibrinogen)'
                analyte = f"{last_analyte} {analyte}"
            elif pending_heading_for_next and ind == 0:  # Cholesterol / Total
                analyte = f"{pending_heading_for_next}, {analyte.lower()}"
            elif headings:  # grouped sub-rows
                analyte = f"{analyte} [{' - '.join(h[1] for h in headings)}]"
            pending_heading_for_next = None

            # next line: unit + factor
            unit = factor = si = ""
            if i + 1 < n and is_factor_line(lines[i + 1]):
                fc = cells(lines[i + 1])
                unit, factor = fc[0], fc[1]
                si = fc[2] if len(fc) > 2 else ""
                i += 2
                # next line: SI unit (no TAB)
                if not si and i < n and "\t" not in lines[i] and clean(lines[i]):
                    si = clean(lines[i])
                    i += 1
            else:
                i += 1
                continue

            if ind == 0:
                last_analyte = c[0]
            rows.append([analyte, specimen, unit, factor, si])
            continue

        # Line without TAB that is not part of a record = heading or note
        ind = indent(line)
        if low.startswith("dual report"):  # note line
            i += 1
            continue
        headings = [h for h in headings if h[0] < ind] + [(ind, txt)]
        pending_heading_for_next = txt if ind == 0 else None
        i += 1

    # de-duplicate, keep order
    seen, out = set(), []
    for r in rows:
        if tuple(r) not in seen:
            seen.add(tuple(r))
            out.append(" ".join(x for x in r if x))

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(HEADER + "\n" + "\n".join(out) + "\n")

    print(f"Rows formatted: {len(out)}")
    print(f"Saved: {OUT_FILE}")


if __name__ == "__main__":
    main()
