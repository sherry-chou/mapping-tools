#!/usr/bin/env python3
"""
ClinicalTrials.gov v2: Single Study JSON -> Flatten -> Vertical Excel (Name/Value)

Description:
    Downloads clinical trial data from ClinicalTrials.gov API v2 and converts
    the nested JSON structure into a flattened vertical Excel format (Name/Value pairs).
    Includes ALL sections: protocolSection, derivedSection, and other metadata.

Usage:
    # Interactive mode (prompts for NCT ID):
    python ctgov_fetch.py

    # With NCT ID as argument:
    python ctgov_fetch.py --nct-id NCT06695026

    # Specify output directory:
    python ctgov_fetch.py --nct-id NCT06695026 --out-dir ./output

    # Specify TS logic file path:
    python ctgov_fetch.py --nct-id NCT06695026 --ts-logic-path /path/to/ctgov_tslogic.xlsx

    # Specify CDISC CT JSON file for value remapping:
    python ctgov_fetch.py --nct-id NCT06695026 --cdisc-ct-path /path/to/cdisclibrary_sdtmct-2026-03-27.json

    # Show help:
    python ctgov_fetch.py --help

Requirements:
    pip install requests pandas openpyxl

Enhancements:
  - Prompt for NCT ID if not provided
  - Validate NCT ID format
  - Decode HTML entities
  - Normalize newlines / remove arrow glyphs
  - Remove bullet prefixes
  - Split eligibility criteria into multiple rows
  - Remove reinserted "⏎" markers by joining multiline content with spaces
  - Process entire study JSON (protocolSection + derivedSection + all other sections)
  - Export to Excel format for better data handling
  - TS sheet with CDISC controlled terminology remapping support
  - TI sheet for eligibility criteria
  - TA sheet for arm group labels
"""

import argparse
import html
import json
import os
import re
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Union

import pandas as pd
import requests


def normalize_text(value: Any, remove_bullets: bool = False) -> str:
    """
    Normalize text by:
    - Decoding HTML entities
    - Normalizing newlines
    - Removing control characters
    - Optionally removing bullet prefixes
    """
    if value is None:
        return ""
    
    s = str(value)
    
    # Decode HTML entities (&gt; -> >, &amp; -> &, etc.)
    s = html.unescape(s)
    
    # Normalize newline-like chars to \n
    s = s.replace('\r\n', '\n')
    s = s.replace('\r', '\n')
    s = s.replace('\u2028', '\n')  # line separator
    s = s.replace('\u2029', '\n')  # paragraph separator
    s = s.replace('\u0085', '\n')  # next line
    
    # Remove/normalize visible return glyphs to newline
    s = s.replace('↵', '\n')
    s = s.replace('⏎', '\n')
    s = s.replace('⤶', '\n')
    
    # Remove other control chars except TAB(9) and LF(10)
    filtered_chars = []
    for char in s:
        c = ord(char)
        if c == 9 or c == 10:  # keep TAB and LF
            filtered_chars.append(char)
        elif c >= 32:  # keep printable
            filtered_chars.append(char)
        # drop others
    
    s = ''.join(filtered_chars)
    
    # Optionally remove bullet/list artifacts at START of each line
    if remove_bullets:
        lines = s.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Remove common bullet prefixes: "o ", bullets, "-", "*", and numbered "1)" "1."
            line = re.sub(r'^(?:[oO]\s+|[•○◦∙·▪■□◆◇►▶▶︎➤➔]\s*|[-–—]\s+|\*\s+)', '', line)
            line = re.sub(r'^(?:\(?\d+\)?[.)]\s+)', '', line)
            
            if line:  # only keep non-empty lines
                cleaned_lines.append(line)
        
        s = '\n'.join(cleaned_lines)
    
    # Trim line-end spaces
    lines = s.split('\n')
    s = '\n'.join(line.rstrip() for line in lines)
    
    return s


def flatten_object(input_object: Any, prefix: str = "") -> Dict[str, Any]:
    """
    Recursively flatten a nested object/dict/list into a flat dictionary with dot notation.
    """
    result = OrderedDict()
    
    # Scalars
    if input_object is None or isinstance(input_object, (str, int, float, bool)):
        key = prefix if prefix else "value"
        result[key] = input_object
        return result
    
    # Arrays/Lists
    if isinstance(input_object, list):
        items = input_object
        
        # Join if scalar-only
        all_scalar = all(
            item is None or isinstance(item, (str, int, float, bool))
            for item in items
        )
        
        if all_scalar:
            result[prefix] = "|".join(str(item) for item in items)
            return result
        
        # Otherwise index + recurse
        for i, item in enumerate(items):
            child_prefix = f"{prefix}[{i}]" if prefix else f"[{i}]"
            child_result = flatten_object(item, child_prefix)
            result.update(child_result)
        
        return result
    
    # Dictionaries/Objects
    if isinstance(input_object, dict):
        for key, value in input_object.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            child_result = flatten_object(value, child_prefix)
            result.update(child_result)
        
        return result
    
    # Default fallback for unknown types
    key = prefix if prefix else "value"
    result[key] = str(input_object)
    return result


def validate_nct_id(nct_id: str) -> bool:
    """Validate NCT ID format: NCT + 8 digits"""
    return bool(re.match(r'^NCT\d{8}$', nct_id))


def load_cdisc_ct(ct_json_path: str) -> Dict[str, Any]:
    """
    Load CDISC Controlled Terminology from JSON file
    
    Args:
        ct_json_path: Path to CDISC CT JSON file
    
    Returns:
        Dictionary with concept IDs as keys and term mappings
    """
    if not ct_json_path or not os.path.exists(ct_json_path):
        return {}
    
    try:
        with open(ct_json_path, 'r', encoding='utf-8') as f:
            ct_data = json.load(f)
        
        # Build a lookup dictionary: conceptId -> term mappings
        ct_lookup = {}
        
        # Handle both single codelist and array of codelists
        codelists = ct_data.get('codelists', [])
        if not codelists and 'conceptId' in ct_data:
            # Single codelist format
            codelists = [ct_data]
        
        for codelist in codelists:
            concept_id = codelist.get('conceptId', '')
            if concept_id:
                # Build forward and reverse mappings
                term_map = {}
                term_concept_map = {}  # Maps submission value to conceptId
                reverse_map = {}
                
                for term in codelist.get('terms', []):
                    preferred_term = term.get('preferredTerm', '')
                    submission_value = term.get('submissionValue', '')
                    term_concept_id = term.get('conceptId', '')
                    synonyms = term.get('synonyms', [])
                    
                    if submission_value:
                        # Map preferredTerm -> submissionValue
                        if preferred_term:
                            term_map[preferred_term.upper()] = submission_value
                        
                        # Map synonyms -> submissionValue
                        for syn in synonyms:
                            term_map[syn.upper()] = submission_value
                        
                        # Map submission value -> term conceptId
                        if term_concept_id:
                            term_concept_map[submission_value.upper()] = term_concept_id
                        
                        # Reverse map: submissionValue -> preferredTerm
                        reverse_map[submission_value.upper()] = preferred_term
                
                ct_lookup[concept_id] = {
                    'term_map': term_map,
                    'term_concept_map': term_concept_map,
                    'reverse_map': reverse_map,
                    'submission_value': codelist.get('submissionValue', ''),
                    'name': codelist.get('name', '')
                }
        
        return ct_lookup
    except Exception as e:
        print(f"Warning: Could not load CDISC CT from {ct_json_path}: {e}")
        return {}


def apply_cdisc_mapping(value: str, logic: str, ct_lookup: Dict[str, Any]) -> tuple:
    """
    Apply CDISC CT mapping to a value based on logic specification
    
    Args:
        value: Original value to map
        logic: Logic string containing C-code reference
        ct_lookup: CDISC CT lookup dictionary
    
    Returns:
        Tuple of (mapped_value, concept_id) or (original_value, '') if no mapping found
    """
    if not value:
        return (value, '')
    
    if not logic:
        return (value, '')
    
    # Extract C-code from logic (e.g., "Map to C-code: C66732")
    c_code_match = re.search(r'C-?code:\s*(C\d+)', logic, re.IGNORECASE)
    c_code = c_code_match.group(1) if c_code_match else None
    
    # First, check for explicit mappings in logic (e.g., "ALL = BOTH", "FEMALE = F")
    # Parse lines like "VALUE = MAPPED_VALUE"
    explicit_mappings = {}
    for line in str(logic).split('\n'):
        mapping_match = re.match(r'^\s*([A-Z0-9\s]+?)\s*=\s*([A-Z0-9]+)\s*$', line.strip(), re.IGNORECASE)
        if mapping_match:
            source_val = mapping_match.group(1).strip()
            target_val = mapping_match.group(2).strip()
            explicit_mappings[source_val.upper()] = target_val
    
    # Apply explicit mapping if found
    value_upper = str(value).upper().strip()
    if value_upper in explicit_mappings:
        mapped_value = explicit_mappings[value_upper]
    else:
        mapped_value = value
    
    # Now look up concept ID in CDISC CT
    concept_id = ''
    if c_code and ct_lookup and c_code in ct_lookup:
        term_map = ct_lookup[c_code].get('term_map', {})
        term_concept_map = ct_lookup[c_code].get('term_concept_map', {})
        
        # Try to map using term_map first
        mapped_upper = mapped_value.upper().strip()
        if mapped_upper in term_map:
            final_value = term_map[mapped_upper]
            concept_id = term_concept_map.get(final_value.upper(), '')
            return (final_value, concept_id)
        
        # If mapped_value is already a submission value, get its concept ID
        if mapped_upper in term_concept_map:
            concept_id = term_concept_map.get(mapped_upper, '')
            return (mapped_value, concept_id)
    
    return (mapped_value, concept_id)


def process_ts_logic(flat: Dict[str, Any], ts_logic_path: str, ct_lookup: Dict[str, Any] = None) -> pd.DataFrame:
    """
    Process TS (Trial Summary) sheet based on logic from ctgov_tslogic.xlsx
    
    Args:
        flat: Flattened JSON data
        ts_logic_path: Path to ctgov_tslogic.xlsx file
        ct_lookup: CDISC Controlled Terminology lookup dictionary
    
    Returns:
        DataFrame with TS data
    """
    if ct_lookup is None:
        ct_lookup = {}
    
    try:
        df_logic = pd.read_excel(ts_logic_path, sheet_name='Sheet1')
    except Exception as e:
        print(f"Warning: Could not read {ts_logic_path}: {e}")
        return pd.DataFrame(columns=['TSPARMCD', 'TSPARM', 'TSVCDREF', 'TSVAL_RAW', 'TSVALCD_RAW', 'NOT_MAPPED'])
    
    ts_rows = []
    
    for idx, row in df_logic.iterrows():
        tsparmcd = row['TSPARMCD']
        tsparm = row['TSPARM']
        tsvcdref = row['TSVCDREF']
        structure_section = row['Structure Section']
        logic = row['Logic']
        
        tsval_raw = ''
        tsvalcd_raw = ''
        not_mapped = ''
        rows_added = False  # Track if we already added rows for this parameter
        
        # Skip if no structure section defined
        if pd.isna(structure_section) or not structure_section.strip():
            not_mapped = 'No endpoint defined'
        else:
            # Handle multiple endpoints (separated by newlines)
            endpoints = [ep.strip() for ep in str(structure_section).split('\n') if ep.strip()]
            
            # Try to find value in flat data
            found = False
            for endpoint in endpoints:
                # Try exact match first
                if endpoint in flat:
                    value = flat[endpoint]
                    
                    # Apply logic if specified
                    if not pd.isna(logic) and logic:
                        logic_str = str(logic).lower()
                        
                        # Handle conditional logic (e.g., "if ... = ...")
                        if 'if ' in logic_str and '=' in logic_str:
                            # For ACTSUB: check if type = "ACTUAL"
                            if 'enrollmentinfo.type' in logic_str and 'actual' in logic_str:
                                type_key = 'protocolSection.designModule.enrollmentInfo.type'
                                if type_key in flat and str(flat[type_key]).upper() == 'ACTUAL':
                                    tsval_raw = str(value)
                                    found = True
                                else:
                                    not_mapped = 'Condition not met'
                            # For COMPTRT: check arm type and get interventionNames
                            elif 'armgroups.type' in logic_str and 'comparator' in logic_str:
                                # This is more complex - need to check arm types and match
                                # For now, mark as not mapped
                                not_mapped = 'Complex logic not implemented'
                            else:
                                # Generic conditional - use the value if endpoint exists
                                tsval_raw = str(value)
                                found = True
                        
                        # Handle format conversions
                        elif 'iso 8601' in logic_str or 'duration format' in logic_str:
                            tsval_raw = str(value)
                            found = True
                        
                        # Handle boolean conversion
                        elif 'boolean' in logic_str:
                            if str(value).lower() == 'true':
                                tsval_raw = 'Y'
                            elif str(value).lower() == 'false':
                                tsval_raw = 'N'
                            else:
                                tsval_raw = str(value)
                            found = True
                        
                        # Handle country format
                        elif 'iso 3166' in logic_str:
                            # Country codes - might need mapping, for now just use value
                            tsval_raw = str(value)
                            found = True
                        
                        else:
                            # Generic logic - just use the value
                            tsval_raw = str(value)
                            found = True
                    else:
                        # No logic, just use the value
                        tsval_raw = str(value)
                        found = True
                    
                    if found:
                        break
                
                # Try with array pattern - look for any endpoint matching pattern without indices
                else:
                    # Create pattern without array indices
                    pattern_no_idx = re.sub(r'\[\d+\]', '', endpoint)
                    # Check if any key in flat starts with this pattern
                    matching_keys = [k for k in flat.keys() if re.sub(r'\[\d+\]', '', k) == pattern_no_idx]
                    
                    if matching_keys:
                        # Check if logic requires counting
                        logic_str_check = str(logic).lower() if not pd.isna(logic) else ''
                        if 'count' in logic_str_check:
                            # Return the count instead of individual values
                            count = len(matching_keys)
                            ts_rows.append({
                                'TSPARMCD': tsparmcd,
                                'TSPARM': tsparm,
                                'TSVCDREF': tsvcdref,
                                'TSVAL_RAW': str(count),
                                'TSVALCD_RAW': '',
                                'NOT_MAPPED': ''
                            })
                            found = True
                            rows_added = True
                        else:
                            # Collect all values and get unique ones
                            all_values = [str(flat[k]) for k in matching_keys if flat[k]]
                            unique_values = list(dict.fromkeys(all_values))  # Preserves order
                            
                            if unique_values:
                                # Create a row for each unique value
                                for unique_val in unique_values:
                                    # Apply CDISC mapping if logic contains C-code
                                    mapped_val, concept_id = apply_cdisc_mapping(unique_val, str(logic), ct_lookup)
                                    
                                    ts_rows.append({
                                        'TSPARMCD': tsparmcd,
                                        'TSPARM': tsparm,
                                        'TSVCDREF': tsvcdref,
                                        'TSVAL_RAW': mapped_val,
                                        'TSVALCD_RAW': concept_id,
                                        'NOT_MAPPED': ''
                                    })
                                found = True
                                rows_added = True
                        break
            
            if not found and not not_mapped:
                not_mapped = 'Endpoint not found in data'
        
        # Only add a single row if no array values were added
        if not rows_added:
            # Apply CDISC mapping if logic contains C-code
            if tsval_raw:
                tsval_raw, tsvalcd_raw = apply_cdisc_mapping(tsval_raw, str(logic), ct_lookup)
            
            ts_rows.append({
                'TSPARMCD': tsparmcd,
                'TSPARM': tsparm,
                'TSVCDREF': tsvcdref,
                'TSVAL_RAW': tsval_raw,
                'TSVALCD_RAW': tsvalcd_raw,
                'NOT_MAPPED': not_mapped
            })
    
    return pd.DataFrame(ts_rows)


def main():
    parser = argparse.ArgumentParser(
        description='Download and flatten ClinicalTrials.gov study data to vertical Excel'
    )
    parser.add_argument(
        '--nct-id',
        type=str,
        help='NCT ID (e.g., NCT06695026)'
    )
    parser.add_argument(
        '--out-dir',
        type=str,
        default='.',
        help='Output directory (default: current directory)'
    )
    parser.add_argument(
        '--ts-logic-path',
        type=str,
        default=None,
        help='Path to ctgov_tslogic.xlsx file (default: ctgov_tslogic.xlsx in output directory)'
    )
    parser.add_argument(
        '--cdisc-ct-path',
        type=str,
        default=None,
        help='Path to CDISC CT JSON file for value remapping (e.g., cdisclibrary_sdtmct-2026-03-27.json)'
    )
    
    args = parser.parse_args()
    
    # Prompt for NCT ID if not provided
    nct_id = args.nct_id
    if not nct_id or not nct_id.strip():
        nct_id = input("Enter NCT ID (e.g., NCT06695026): ")
    
    # Normalize input (trim spaces)
    nct_id = nct_id.strip()
    
    # Validate NCT ID format
    if not validate_nct_id(nct_id):
        print(f"Error: Invalid NCT ID format: '{nct_id}'. Expected format: NCT######## (example: NCT06695026)")
        sys.exit(1)
    
    # Ensure output directory exists
    out_dir = args.out_dir
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    
    # Build URL and output file path
    url = f"https://clinicaltrials.gov/api/v2/studies/{nct_id}"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_excel = os.path.join(out_dir, f"{nct_id}_vertical_{stamp}.xlsx")
    
    # Download JSON from ClinicalTrials.gov v2 endpoint
    print(f"Fetching data from {url}...")
    try:
        response = requests.get(url)
        response.raise_for_status()
        study = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error downloading data: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        sys.exit(1)
    
    # Flatten entire study object (includes protocolSection, derivedSection, etc.)
    flat = flatten_object(study)
    
    # Extract eligibility criteria for TI sheet
    eligibility_criteria_raw = flat.get("protocolSection.eligibilityModule.eligibilityCriteria", "")
    ti_rows = []
    
    if eligibility_criteria_raw:
        # First normalize the text but keep structure to identify sections
        raw_text = str(eligibility_criteria_raw)
        
        # Split by lines to track sections
        lines = raw_text.split('\n')
        current_category = None
        
        for line in lines:
            line_stripped = line.strip()
            
            # Check if this is a section header
            if 'Inclusion Criteria:' in line:
                current_category = 'INCLUSION'
                continue  # Skip the header line itself
            elif 'Exclusion Criteria:' in line:
                current_category = 'EXCLUSION'
                continue  # Skip the header line itself
            
            # Skip empty lines
            if not line_stripped:
                continue
            
            # Process the criterion line
            normalized_line = normalize_text(line_stripped, remove_bullets=True)
            if normalized_line:
                ti_rows.append({
                    'IECAT': current_category if current_category else '',
                    'IETEST_FULL': normalized_line
                    
                })
    
    # Build vertical rows, splitting Eligibility Criteria into multiple rows
    rows = []
    ta_rows = []  # For arm group labels
    
    for key in sorted(flat.keys()):
        val = flat[key]
        
        # Create endpoint by removing array indices [0], [1], etc.
        endpoint = re.sub(r'\[\d+\]', '', key)
        
        # Collect arm group labels for TA sheet
        if endpoint == "protocolSection.armsInterventionsModule.armGroups.label":
            ta_rows.append({'ARM': val})
        
        if key == "protocolSection.eligibilityModule.eligibilityCriteria":
            text = normalize_text(val, remove_bullets=True)
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            # Fallback split by "*" if still packed
            if len(lines) <= 2 and '*' in text:
                lines = [line.strip() for line in text.split('*') if line.strip()]
            
            for i, line in enumerate(lines, start=1):
                rows.append({
                    'IndexField': endpoint,
                    'Name': key,
                    'LineNo': i,
                    'Value': line
                })
            
            continue
        
        # Default: normalize and remove bullets
        norm = normalize_text(val, remove_bullets=True)
        
        # Join multiline content with spaces (NO ⏎ marker)
        if '\n' in norm:
            norm = ' '.join(line.strip() for line in norm.split('\n') if line.strip())
        
        rows.append({
            'IndexField': endpoint,
            'Name': key,
            'LineNo': '',
            'Value': norm
        })
    
    # Export to Excel with multiple sheets
    df_main = pd.DataFrame(rows)
    df_ti = pd.DataFrame(ti_rows) if ti_rows else pd.DataFrame(columns=['IECAT', 'IETEST_FULL'])
    df_ta = pd.DataFrame(ta_rows) if ta_rows else pd.DataFrame(columns=['ARM'])
    
    # Load CDISC CT if provided
    ct_lookup = {}
    if args.cdisc_ct_path:
        print(f"Loading CDISC CT from: {args.cdisc_ct_path}")
        ct_lookup = load_cdisc_ct(args.cdisc_ct_path)
        if ct_lookup:
            print(f"Loaded {len(ct_lookup)} CDISC CT codelists")
    
    # Process TS sheet using ctgov_tslogic.xlsx
    ts_logic_path = args.ts_logic_path if args.ts_logic_path else os.path.join(out_dir, 'ctgov_tslogic.xlsx')
    df_ts = process_ts_logic(flat, ts_logic_path, ct_lookup)
    
    # Report CDISC CT mapping stats if CT was provided
    if args.cdisc_ct_path and ct_lookup:
        mapped_with_cd = (df_ts['TSVALCD_RAW'] != '').sum()
        print(f"TS rows with CDISC C-code populated: {mapped_with_cd:,}")
    
    with pd.ExcelWriter(out_excel, engine='openpyxl') as writer:
        df_main.to_excel(writer, sheet_name='AllContents', index=False)
        df_ti.to_excel(writer, sheet_name='TI', index=False)
        df_ta.to_excel(writer, sheet_name='TA', index=False)
        df_ts.to_excel(writer, sheet_name='TS', index=False)
    
    print(f"Saved vertical Excel to: {out_excel}")
    print(f"Total rows: {len(rows):,}")
    print(f"TI sheet rows: {len(ti_rows):,}")
    print(f"TA sheet rows: {len(ta_rows):,}")
    print(f"TS sheet rows: {len(df_ts):,}")
    print(f"TS mapped rows: {(df_ts['NOT_MAPPED'] == '').sum():,}")
    print(f"TS not mapped rows: {(df_ts['NOT_MAPPED'] != '').sum():,}")


if __name__ == '__main__':
    main()
