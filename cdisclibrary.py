"""
CDISC Library API Data Fetcher

This script fetches data from the CDISC Library API and saves the response to a JSON file.

Parameters:
    --endpoint (required)    : API endpoint path (e.g., /ct/packages, /products, /root/products)
    --path (required)        : Query path for the specific resource 
                              (e.g., /sdtmct-2026-03-27, /Terminology, /sdtmig-3-4)
    --output-dir (optional)  : Output directory path (default: same directory as script)

API Documentation:
    For available endpoints and paths, refer to: https://api.developer.library.cdisc.org/

Example Usage:
    # Fetch SDTM Controlled Terminology package
    python cdisclibrary.py --endpoint /ct/packages --path /sdtmct-2026-03-27
    
    # Fetch Terminology products
    python cdisclibrary.py --endpoint /products --path /Terminology
    
    # Fetch SDTM Implementation Guide with custom output directory
    python cdisclibrary.py --endpoint /root/products --path /sdtmig-3-4 --output-dir /data/cdisc
    
    # Fetch ADaM Controlled Terminology
    python cdisclibrary.py --endpoint /ct/packages --path /adamct-2024-09-27

Output:
    JSON file named: cdisclibrary_<path-without-slashes>.json
    Example: cdisclibrary_sdtmct-2026-03-27.json
"""

import requests
import json
import os
import argparse

# Set up argument parser for output path and query parameters
parser = argparse.ArgumentParser(
    description='Fetch CDISC library data and save to JSON',
    epilog='For available endpoints and paths, refer to: https://api.developer.library.cdisc.org/')
parser.add_argument('--output-dir', type=str, default=None,
                    help='Output directory path (default: same directory as script)')
parser.add_argument('--endpoint', type=str, required=True,
                    help='API endpoint path (e.g., /ct/packages, /products)')
parser.add_argument('--path', type=str, required=True,
                    help='Query path (e.g., /sdtmct-2026-03-27, /Terminology)')
args = parser.parse_args()

# Determine output directory
if args.output_dir:
    output_dir = args.output_dir
else:
    # Default to the same directory as the script
    output_dir = os.path.dirname(os.path.abspath(__file__))

baseURL = "https://library.cdisc.org/api/mdr"
queryEndpoint = args.endpoint
queryPath = args.path

# Make the API request
req = requests.get(baseURL + queryEndpoint + queryPath, headers={'api-key': '09cc99d2273a4316892c489d38d62d57', 'Accept': 'application/json'})

# Check if request was successful
if req.status_code == 200:
    # Create filename from queryPath (remove leading slash)
    filename = f"cdisclibrary_{queryPath.lstrip('/')}.json"
    output_path = os.path.join(output_dir, filename)
    
    # Save the JSON response to file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(req.json(), f, indent=2, ensure_ascii=False)
    
    print(f"Data successfully saved to: {output_path}")
else:
    print(f"Error: Request failed with status code {req.status_code}")
    print(f"Response: {req.text}")