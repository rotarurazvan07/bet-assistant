#!/usr/bin/env python3
"""
Test script for manually testing the _scrape_match_odds function with a given URL.
Saves the HTML of the scraped page for debugging purposes.
"""

import sys
import os
import json
import datetime
from odds_enricher import _scrape_match_odds
from scrape_kit import browser

def save_html_content(session, url, output_dir="html_artifacts"):
    """Save the HTML content of the current page to a file."""
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Get the current page HTML
    html_content = session.page.content()

    # Generate a filename based on URL and timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # Extract a clean identifier from the URL
    url_part = url.split("//")[-1].split("/")[0].replace(".", "_")
    filename = f"scraped_{url_part}_{timestamp}.html"
    filepath = os.path.join(output_dir, filename)

    # Save the HTML content
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Saved HTML content to: {filepath}")
    return filepath

def test_scrape_match_odds(odds_url):
    """Test the _scrape_match_odds function with a given URL."""
    print(f"Testing _scrape_match_odds with URL: {odds_url}")

    # Create a browser session
    with browser(solve_cloudflare=True, interactive=True) as session:
        try:
            # Scrape the odds
            odds = _scrape_match_odds(session, odds_url)
            html_filepath = save_html_content(session, odds_url)

            # Print the results
            print("Scraped odds:")
            print(json.dumps(odds, indent=2))

            # Add the HTML filepath to the results
            if odds:
                odds['_html_artifact'] = html_filepath

            return odds
        except Exception as e:
            print(f"Error: {e}")
            return None

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_odds_scraping.py <odds_url>")
        sys.exit(1)

    odds_url = sys.argv[1]
    test_scrape_match_odds(odds_url)