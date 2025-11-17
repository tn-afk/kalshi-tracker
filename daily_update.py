#!/usr/bin/env python3
"""
Kalshi Daily Data Updater for Render
Checks for new Kalshi data and updates Google Sheet
"""
import json
import os
import sys
from datetime import datetime, timedelta
from io import StringIO
import requests
from google.oauth2.credentials import Credentials

# Configuration from environment variables
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', '1HzPlGwvV9G0mMTEUibI_8WecxgWwK-zfCNr0tGS-q2I')
GOOGLE_TOKEN = os.getenv('GOOGLE_ACCESS_TOKEN')
GOOGLE_REFRESH_TOKEN = os.getenv('GOOGLE_REFRESH_TOKEN')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
MAJOR_US_SPORTS = ['NBA', 'NFL', 'NCAA', 'MLB', 'MLS', 'NHL']

# Use /tmp for temporary files on Render
RESULTS_FILE = '/tmp/kalshi_tracking_results.json'

def get_access_token():
    """Get or refresh Google OAuth access token"""
    if not all([GOOGLE_REFRESH_TOKEN, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET]):
        raise ValueError("Missing Google OAuth credentials in environment variables")

    # Create credentials object
    creds = Credentials(
        token=None,  # Start with no token to force refresh
        refresh_token=GOOGLE_REFRESH_TOKEN,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET
    )

    # Always refresh to get a fresh token
    from google.auth.transport.requests import Request
    creds.refresh(Request())

    return creds.token

def check_and_download_new_data(date_str):
    """Check if data exists for a given date and download if available"""
    json_url = f"https://kalshi-public-docs.s3.amazonaws.com/reporting/market_data_{date_str}.json"

    print(f"Checking for data on {date_str}...", flush=True)

    try:
        response = requests.get(json_url, timeout=300)
        if response.status_code == 200:
            print(f"✓ Downloaded data for {date_str}", flush=True)
            return response.json()
        else:
            print(f"✗ No data available for {date_str} (HTTP {response.status_code})", flush=True)
            return None
    except Exception as e:
        print(f"✗ Error downloading {date_str}: {e}", flush=True)
        return None

def process_data(data, date_str):
    """Process downloaded data and calculate metrics"""
    try:
        total_volume = sum(record.get('daily_volume', 0) for record in data)

        major_sports_volume = sum(
            record.get('daily_volume', 0)
            for record in data
            if any(sport in record.get('ticker_name', '') for sport in MAJOR_US_SPORTS)
        )

        kxmve_volume = sum(
            record.get('daily_volume', 0)
            for record in data
            if 'KXMVE' in record.get('ticker_name', '')
        )

        return {
            'date': date_str,
            'status': 'success',
            'total_volume': total_volume,
            'major_sports_volume': major_sports_volume,
            'kxmve_volume': kxmve_volume
        }
    except Exception as e:
        print(f"Error processing {date_str}: {e}", flush=True)
        return None

def update_google_sheet(token, spreadsheet_id, new_rows):
    """Append new rows to the bottom of the Google Sheet"""
    # Get existing data to find the next row
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/Kalshi Data!A:D'
    headers = {'Authorization': f'Bearer {token}'}

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    existing_data = response.json().get('values', [])
    next_row = len(existing_data) + 1

    # Append new rows
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/Kalshi Data!A{next_row}:append'
    body = {'values': new_rows}
    params = {'valueInputOption': 'RAW'}

    response = requests.post(url, headers=headers, json=body, params=params)
    response.raise_for_status()

    print(f"✓ Added {len(new_rows)} new row(s) to Google Sheet", flush=True)

def main():
    print(f"=== Kalshi Daily Update - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n", flush=True)

    # Load existing results if available
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'r') as f:
            all_results = json.load(f)
        latest_date = datetime.strptime(all_results[0]['date'], '%Y-%m-%d')
    else:
        all_results = []
        latest_date = datetime(2025, 11, 8)  # Start from Nov 8

    # Check for new dates (up to 7 days ahead to catch up if script wasn't run)
    new_data_found = []
    for i in range(1, 8):
        check_date = latest_date + timedelta(days=i)
        date_str = check_date.strftime('%Y-%m-%d')

        data = check_and_download_new_data(date_str)
        if data:
            result = process_data(data, date_str)
            if result:
                new_data_found.append(result)
                print(f"  Total: {result['total_volume']:,}", flush=True)

    if not new_data_found:
        print("\nNo new data available. Sheet is up to date.", flush=True)
        return

    # Update results file (keep newest first for tracking)
    all_results = new_data_found + all_results
    with open(RESULTS_FILE, 'w') as f:
        json.dump(all_results, f, indent=2)

    print(f"\nFound {len(new_data_found)} new day(s) of data", flush=True)

    # Update Google Sheet
    print("\nUpdating Google Sheet...", flush=True)
    token = get_access_token()

    new_rows = []
    for result in new_data_found:
        new_rows.append([
            result['date'],
            result['total_volume'],
            result['major_sports_volume'],
            result['kxmve_volume']
        ])

    update_google_sheet(token, SPREADSHEET_ID, new_rows)

    print("\n✓ Daily update complete!", flush=True)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
