import re
import pandas as pd

# Raw text captured from the AMA "Units of measure converter" page (Table 2 section)
# Source: https://academic.oup.com/amamanualofstyle/si-conversion-calculator (Table 2)
# (Full Table 2 text is embedded below in 'raw'.)
raw = r"""
[Table 2 full text exactly as retrieved from the page… omitted here for brevity in this snippet;
in my run I included the entire text block, which you can paste here exactly as in the file.]
"""

# --- Parsing logic ---
# Clean text: normalize whitespace
s = raw.replace('\xa0',' ').replace('\u2009',' ')
s = re.sub(r"\s+"," ", s)

# Tokenize
tokens = s.split(' ')

# Helpers
num_re = re.compile(r'^[<>]?\d+(?:\.\d+)?$')
def is_number(tok): return bool(num_re.match(tok))

# SI-unit detector (common endings)
si_patterns = [
    r'^(?:p|n|μ|m|k)?mol/L$', r'^(?:p|n|μ|m)?kat/L$', r'^(?:m)?Eq/L$', r'^kU/L$', r'^U/L$',
    r'^ng/L$', r'^μg/L$', r'^mg/L$', r'^g/L$', r'^IU/L$', r'^kPa$', r'^fL$',
    r'^mmol/kg$', r'^×109/L$', r'^×1012/L$', r'^mL/s/m2$', r'^μmol/d$', r'^μg/24$',
    r'^nkat/g$', r'^nkat/g hemoglobin$'
]
si_res = [re.compile(p) for p in si_patterns]

def looks_like_si(tok1, tok2=None, tok3=None):
    if any(r.match(tok1) for r in si_res):
        return 1, tok1
    # Special: 'Proportion of 1.0'
    if tok1 == 'Proportion' and tok2 == 'of' and (tok3 or '').startswith('1'):
        return 3, 'Proportion of 1.0'
    return 0, ''

SPEC_HINTS = {
    'serum','plasma','whole','blood','urine','stool','arterial','red',
    'cells','cell','erythrocyte','erythrocytes'
}

records, head_tokens = [], []
i = 0
while i < len(tokens):
    t = tokens[i]
    if is_number(t) and i+1 < len(tokens):
        step, siu = looks_like_si(tokens[i+1],
                                  tokens[i+2] if i+2 < len(tokens) else None,
                                  tokens[i+3] if i+3 < len(tokens) else None)
        if step:
            head = ' '.join(head_tokens).strip()
            head_parts = head.split(' ')
            if len(head_parts) >= 2:
                conv_unit = head_parts[-1]
                analyte_spec = ' '.join(head_parts[:-1])
            else:
                conv_unit = ''
                analyte_spec = head

            # Split analyte vs specimen using specimen hints (rightmost start)
            asp_toks = analyte_spec.split()
            split_pos = None
            for j in range(len(asp_toks)):
                tj = asp_toks[j].lower().strip(',')
                if tj in SPEC_HINTS:
                    split_pos = j
                    if j > 0 and asp_toks[j-1].lower() in {'whole','arterial','red'}:
                        split_pos = j-1
                    break
            if split_pos is not None:
                analyte = ' '.join(asp_toks[:split_pos]).strip(', ')
                specimen = ' '.join(asp_toks[split_pos:]).strip(', ')
            else:
                analyte = analyte_spec.strip(', ')
                specimen = ''

            # Filter obvious headings
            bad_prefixes = ('Units of measure converter', 'Table 1:', 'Conventional units', 'Blood gases')
            if analyte and not analyte.startswith(bad_prefixes):
                records.append([analyte, specimen, conv_unit, t, siu])

            i += 1 + step
            head_tokens = []
            continue

    head_tokens.append(t)
    i += 1

# Build DataFrame and clean
cols = ["Analyte","Specimen","Conventional Unit","Conversion Factor","SI Unit"]
df = pd.DataFrame(records, columns=cols)

# Drop noise and duplicates
for c in ['Analyte','Specimen','Conventional Unit','SI Unit']:
    df[c] = df[c].str.replace(r"\s+,","", regex=True).str.strip()
df = df.drop_duplicates().sort_values(by=['Analyte','Specimen']).reset_index(drop=True)

# Save
df.to_excel("AMA_Table2_full.xlsx", index=False)
print("Rows parsed:", len(df))
print("Saved:", "AMA_Table2_full.xlsx")
``