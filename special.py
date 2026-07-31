#!/usr/bin/env python3
"""
Program: special.py
Purpose: Detect and report non-ASCII characters and hex-text patterns before &quot; in XML files
Author:  pic0sxc30
Date:    July 30, 2026
Version: 1.2

Description:
    This script scans XML or text files to identify problematic character sequences
    that appear immediately before the &quot; entity. It detects:
    1. Non-ASCII characters (outside the standard ASCII range U+0000-U+007F)
    2. Literal hex-text patterns (e.g., xE2x80) that may indicate double-encoding

Usage:
    python special.py <input_file> [options]
    python special.py -h  # for help

Examples:
    # Console output only (as before)
    python special.py "define 2.xml"
    python special.py input.xml --context-width 60

    # Save results to Excel
    python special.py input.xml --output results.xlsx

    # Both custom context width and Excel output
    python special.py input.xml -o output.xlsx -w 50

Output:
    For each match found, the script reports:
    - Line number
    - Type of match (Non-ASCII or hex-text)
    - The actual sequence found
    - Unicode code points (for non-ASCII)
    - Surrounding context
    - Optional: Export results to Excel file

Notes:
    - Uses UTF-8 encoding with error replacement for reading files
    - Context window defaults to 40 characters on each side of the match
    - Excel output requires pandas and openpyxl packages
"""

import re
import argparse
import sys
import os

# Pattern: one or more non-ASCII chars immediately before &quot;
# [^\x00-\x7F]+  = one or more bytes outside ASCII
# (?=&quot;)     = must be directly followed by &quot; (lookahead)
pattern_nonascii_before_quot = re.compile(r'([^\x00-\x7F]+)(?=&quot;)')

# Optional: also catch literal text sequences like xE2x80 before &quot;
pattern_hextext_before_quot = re.compile(r'(?:x[0-9A-Fa-f]{2})+(?=&quot;)')

def show_context(line, start, end, width=40):
    """Return a short context window around the match."""
    s = max(0, start - width)
    e = min(len(line), end + width)
    return line[s:e].replace('\n', '')

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Detect non-ASCII characters and hex-text patterns before &quot; in XML files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "define 2.xml"
  %(prog)s input.xml --context-width 60
  %(prog)s data.xml -w 30
  %(prog)s input.xml --output results.xlsx
  %(prog)s input.xml -o output.xlsx -w 50
        """
    )
    
    parser.add_argument(
        'input_file',
        help='Input file to scan (typically an XML file)'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='Output Excel file to save results (e.g., results.xlsx)'
    )
    
    parser.add_argument(
        '-w', '--context-width',
        type=int,
        default=40,
        help='Number of characters to show on each side of match (default: 40)'
    )
    
    parser.add_argument(
        '-v', '--version',
        action='version',
        version='%(prog)s 1.2'
    )
    
    return parser.parse_args()

def main():
    """Main execution function."""
    args = parse_arguments()
    
    # List to store results for Excel output
    results = []
    
    try:
        with open(args.input_file, encoding="utf-8", errors="replace") as f:
            match_count = 0
            
            for lineno, line in enumerate(f, 1):
                # First: true non-ASCII characters immediately before &quot;
                for m in pattern_nonascii_before_quot.finditer(line):
                    seq = m.group(1)
                    ctx = show_context(line, m.start(), m.end(), args.context_width)
                    # Show code points for debug
                    codepoints = " ".join(f"U+{ord(c):04X}" for c in seq)
                    
                    print(f"[Line {lineno}] Non-ASCII before &quot;: {repr(seq)} ({codepoints})")
                    print(f"  Context: …{ctx}…\n")
                    
                    # Store result for Excel
                    results.append({
                        'Line Number': lineno,
                        'Match Type': 'Non-ASCII',
                        'Sequence': repr(seq),
                        'Code Points': codepoints,
                        'Context': ctx
                    })
                    match_count += 1

                # Second: literal hex-text like xE2x80 (double-encoded style) before &quot;
                for m in pattern_hextext_before_quot.finditer(line):
                    seq = m.group(0)
                    ctx = show_context(line, m.start(), m.end(), args.context_width)
                    
                    print(f"[Line {lineno}] Literal hex-text before &quot;: {seq}")
                    print(f"  Context: …{ctx}…\n")
                    
                    # Store result for Excel
                    results.append({
                        'Line Number': lineno,
                        'Match Type': 'Hex-text',
                        'Sequence': seq,
                        'Code Points': 'N/A',
                        'Context': ctx
                    })
                    match_count += 1
            
            if match_count == 0:
                print(f"No problematic patterns found in {args.input_file}")
            else:
                print(f"Total matches found: {match_count}")
            
            # Write to Excel if output file specified
            if args.output and results:
                try:
                    import pandas as pd
                    df = pd.DataFrame(results)
                    df.to_excel(args.output, index=False, sheet_name='Results')
                    print(f"\nResults saved to: {os.path.abspath(args.output)}")
                except ImportError:
                    print("\nWarning: pandas not installed. Cannot create Excel file.", file=sys.stderr)
                    print("Install with: pip install pandas openpyxl", file=sys.stderr)
                except Exception as e:
                    print(f"\nError writing Excel file: {e}", file=sys.stderr)
            elif args.output and not results:
                print(f"\nNo results to save. Excel file not created.")
                
    except FileNotFoundError:
        print(f"Error: File '{args.input_file}' not found.", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: Permission denied reading '{args.input_file}'.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
