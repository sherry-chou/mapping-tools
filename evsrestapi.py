#!/usr/bin/env python3
"""
EVS REST API Client
Provides a simple interface to query the NCI EVS REST API

API Documentation: https://evsexplore.semantics.cancer.gov/evsexplore/evsapi
Base URL: https://api-evsrest.nci.nih.gov/api/v1/concept/

Usage:
    Single-word search terms:
        python evsrestapi.py --searchterm ibuprofen
        python evsrestapi.py --terminology ncit --searchterm melanoma
    
    Multi-word search terms (use quotes):
        python evsrestapi.py --searchterm "Nucleoside Analog"
        python evsrestapi.py --searchterm "Decreased RNA Replication"
        python evsrestapi.py --terminology ncit --searchterm "lung cancer"
    
    Additional options:
        python evsrestapi.py --searchterm aspirin --type match --include summary --pageSize 20
        python evsrestapi.py --searchterm ibuprofen --output results/ --no-save

Required Parameters:
    --searchterm: The term to search for (use quotes for multi-word terms)

Optional Parameters:
    --terminology: Terminology to search (medrt, ncit, ncim) [default: medrt]
    --type: Search type (contains, match, startsWith, phrase, fuzzy, AND, OR) [default: contains]
    --include: Detail level (minimal, summary, full, custom) [default: minimal]
    --pageSize: Number of results per page [default: 10]
    --fromRecord: Starting record for pagination [default: 0]
    --output: Output directory for JSON file [default: current directory]
    --no-save: Print results only, do not save to file

Author: pic0sxc30
Date: July 31, 2026
"""

import requests
import json
from typing import Optional, Dict, Any
from urllib.parse import urljoin
from datetime import datetime
import os
import argparse


class EVSRestAPI:
    """Client for interacting with the NCI EVS REST API"""
    
    BASE_URL = "https://api-evsrest.nci.nih.gov/api/v1/concept/"
    
    def __init__(self):
        """Initialize the EVS REST API client"""
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'EVSRestAPI-Python-Client/1.0',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
    
    def search(
        self,
        terminology: str,
        searchterm: str,
        type: str = "contains",
        include: str = "minimal",
        fromRecord: int = 0,
        pageSize: int = 10
    ) -> Dict[str, Any]:
        """
        Search for concepts in the specified terminology
        
        Parameters:
        -----------
        terminology : str
            The terminology to search (e.g., 'medrt', 'ncit', 'ncim')
        searchterm : str
            The term to search for (e.g., 'acetaminophen')
        type : str, optional
            The search type (default: 'contains')
            Options: 'contains', 'match', 'startsWith', 'phrase', 'fuzzy', 'AND', 'OR'
        include : str, optional
            Level of detail to include (default: 'minimal')
            Options: 'minimal', 'summary', 'full', 'custom'
        fromRecord : int, optional
            Starting record number for pagination (default: 0)
        pageSize : int, optional
            Number of results per page (default: 10)
        
        Returns:
        --------
        dict
            JSON response from the API
        """
        endpoint = f"{terminology}/search"
        url = urljoin(self.BASE_URL, endpoint)
        
        params = {
            'term': searchterm,
            'type': type,
            'include': include,
            'fromRecord': fromRecord,
            'pageSize': pageSize
        }
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making API request: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response: {e.response.text}")
            raise
    
    def get_concept(
        self,
        terminology: str,
        code: str,
        include: str = "summary"
    ) -> Dict[str, Any]:
        """
        Get a specific concept by code
        
        Parameters:
        -----------
        terminology : str
            The terminology (e.g., 'medrt', 'ncit')
        code : str
            The concept code
        include : str, optional
            Level of detail (default: 'summary')
        
        Returns:
        --------
        dict
            JSON response from the API
        """
        endpoint = f"{terminology}/{code}"
        url = urljoin(self.BASE_URL, endpoint)
        
        params = {'include': include}
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making API request: {e}")
            raise
    
    def save_to_file(self, data: Dict[str, Any], terminology: str, output_dir: str = ".") -> str:
        """
        Save JSON results to a file with date-based naming
        
        Parameters:
        -----------
        data : dict
            The data to save
        terminology : str
            The terminology name (e.g., 'medrt', 'ncit')
        output_dir : str, optional
            Directory to save the file (default: current directory)
        
        Returns:
        --------
        str
            Path to the saved file
        """
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename with current date
        current_date = datetime.now().strftime("%Y%m%d")
        filename = f"{terminology}_{current_date}.json"
        filepath = os.path.join(output_dir, filename)
        
        # Save JSON data to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Results saved to: {filepath}")
        return filepath


def main():
    """Example usage of the EVS REST API client"""
    
    parser = argparse.ArgumentParser(
        description='Search the NCI EVS REST API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s --searchterm ibuprofen
  %(prog)s --searchterm "Nucleoside Analog"
  %(prog)s --terminology ncit --searchterm "Decreased RNA Replication"
  %(prog)s --terminology ncit --searchterm melanoma --type match --pageSize 20
  %(prog)s --searchterm aspirin --include summary --output results/
        '''
    )
    
    parser.add_argument(
        '--terminology',
        default='medrt',
        help='Terminology to search (e.g., medrt, ncit, ncim). Default: medrt'
    )
    parser.add_argument(
        '--searchterm',
        required=True,
        help='Term to search for (required). Use quotes for multi-word terms.'
    )
    parser.add_argument(
        '--type',
        default='contains',
        choices=['contains', 'match', 'startsWith', 'phrase', 'fuzzy', 'AND', 'OR'],
        help='Search type. Default: contains'
    )
    parser.add_argument(
        '--include',
        default='minimal',
        choices=['minimal', 'summary', 'full', 'custom'],
        help='Level of detail to include. Default: minimal'
    )
    parser.add_argument(
        '--pageSize',
        type=int,
        default=10,
        help='Number of results per page. Default: 10'
    )
    parser.add_argument(
        '--fromRecord',
        type=int,
        default=0,
        help='Starting record number for pagination. Default: 0'
    )
    parser.add_argument(
        '--output',
        default='.',
        help='Output directory for JSON file. Default: current directory'
    )
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Do not save results to file, only print to console'
    )
    
    args = parser.parse_args()
    
    # Create API client
    api = EVSRestAPI()
    
    # Search
    print("=" * 80)
    print(f"Searching for '{args.searchterm}' in {args.terminology.upper()}")
    print("=" * 80)
    
    results = api.search(
        terminology=args.terminology,
        searchterm=args.searchterm,
        type=args.type,
        include=args.include,
        fromRecord=args.fromRecord,
        pageSize=args.pageSize
    )
    
    total_results = results.get('total', 0)
    concepts = results.get('concepts', [])
    
    if total_results == 0:
        print("\n❌ No result was found.")
        return
    
    print(f"\nFound {total_results} results")
    
    # Save results to file unless --no-save is specified
    if not args.no_save:
        saved_file = api.save_to_file(
            results, 
            terminology=args.terminology,
            output_dir=args.output
        )
        print(f"✓ Results saved to: {saved_file}")
    else:
        # Only print results to terminal when --no-save is used
        print(f"\nShowing {len(concepts)} results:\n")
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
