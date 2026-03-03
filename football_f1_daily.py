#!/usr/bin/env python3
"""
Kalshi Football & F1 Daily Tracker for Render
Checks for new Kalshi data and updates Google Sheet
Uses streaming JSON parsing to stay within 512MB memory limit
"""
import os
import sys
import gc
from datetime import datetime, timedelta
import requests
import ijson
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Configuration from environment variables
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', '1HzPlGwvV9G0mMTEUibI_8WecxgWwK-zfCNr0tGS-q2I')
SHEET_NAME = 'Football & F1'
GOOGLE_REFRESH_TOKEN = os.getenv('GOOGLE_REFRESH_TOKEN')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

# Football/F1 filters (Kalshi uses KX prefix)
FILTERS = ['KXUCL', 'KXMLS', 'KXEPL', 'KXLALIGA', 'KXBUNDESLIGA', 'KXSERIEA',
           'KXLIGUE1', 'KXUEL', 'KXUEFA', 'KXCLUBWC', 'KXFACUP', 'KXEFLCUP', 'KXF1']

TEMP_FILE = '/tmp/kalshi_football_temp.json'


def get_access_token():
    """Get or refresh Google OAuth access token"""
    if not all([GOOGLE_REFRESH_TOKEN, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET]):
        raise ValueError("Missing Google OAuth credentials in environment variables")

    creds = Credentials(
        token=None,
        refresh_token=GOOGLE_REFRESH_TOKEN,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET
    )
    creds.refresh(Request())
    return creds.token


def process_date(date_str):
    """Download and process data for one date using streaming JSON parsing"""
    url = f"https://kalshi-public-docs.s3.amazonaws.com/reporting/market_data_{date_str}.json"

    print(f"[{date_str}] Checking... ", end='', flush=True)

    try:
        # Download to temp file (streaming to avoid memory spike)
        response = requests.get(url, timeout=300, stream=True)
        if response.status_code != 200:
            print(f"No data (HTTP {response.status_code})")
            return None

        print("Downloading... ", end='', flush=True)
        with open(TEMP_FILE, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1048576):
                f.write(chunk)
        response.close()

        print("Processing... ", end='', flush=True)

        # Stream-parse the JSON file — never loads full array into memory
        total_volume = 0
        with open(TEMP_FILE, 'rb') as f:
            for record in ijson.items(f, 'item'):
                ticker = record.get('report_ticker', '').upper()
                if any(ticker.startswith(flt) for flt in FILTERS):
                    total_volume += record.get('daily_volume', 0)

        # Clean up
        os.remove(TEMP_FILE)
        gc.collect()

        print(f"Volume: {total_volume:,}")
        return {'date': date_str, 'volume': total_volume}

    except requests.exceptions.Timeout:
        print("Timeout")
        if os.path.exists(TEMP_FILE):
            os.remove(TEMP_FILE)
        return None
    except Exception as e:
        print(f"Error: {e}")
        if os.path.exists(TEMP_FILE):
            os.remove(TEMP_FILE)
        return None


def update_google_sheet(token, rows):
    """Append rows to Google Sheet"""
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/Football & F1!A:B'
    headers = {'Authorization': f'Bearer {token}'}

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    existing = response.json().get('values', [])
    next_row = len(existing) + 1

    url = f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/Football & F1!A{next_row}:append'
    body = {'values': [[r['date'], r['volume']] for r in rows]}
    params = {'valueInputOption': 'RAW'}

    response = requests.post(url, headers=headers, json=body, params=params)
    response.raise_for_status()
    print(f"Added {len(rows)} row(s) to Google Sheet")


def main():
    print(f"=== Football & F1 Daily Update - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    print(f"Tracking: {', '.join(FILTERS)}\n")

    # Get latest date from sheet
    try:
        print("Checking Google Sheet for latest date...", flush=True)
        token = get_access_token()
        url = f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/Football & F1!A:A'
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        dates = response.json().get('values', [])
        if len(dates) > 1:
            latest_date_str = dates[-1][0]
            latest_date = datetime.strptime(latest_date_str, '%Y-%m-%d')
            print(f"Latest date in sheet: {latest_date_str}\n")
        else:
            latest_date = datetime(2025, 12, 19)
            print(f"No data in sheet, starting from {latest_date.strftime('%Y-%m-%d')}\n")
    except Exception as e:
        print(f"Error reading sheet: {e}")
        latest_date = datetime(2025, 12, 19)

    # Calculate how many days to catch up (dynamic, up to 60 days)
    days_behind = (datetime.now() - latest_date).days
    catchup_days = min(days_behind, 60)
    print(f"Days to catch up: {catchup_days}\n", flush=True)

    # Process each missing date and upload in batches of 5
    new_data = []
    for i in range(1, catchup_days + 1):
        check_date = latest_date + timedelta(days=i)
        if check_date > datetime.now():
            break
        date_str = check_date.strftime('%Y-%m-%d')
        result = process_date(date_str)
        if result:
            new_data.append(result)

        # Upload in batches of 5 to avoid losing progress
        if len(new_data) >= 5:
            print(f"\nUploading batch of {len(new_data)} days...")
            token = get_access_token()
            update_google_sheet(token, new_data)
            new_data = []

    # Upload remaining data
    if new_data:
        print(f"\nUploading final {len(new_data)} day(s)...")
        token = get_access_token()
        update_google_sheet(token, new_data)

    if not new_data and catchup_days <= 0:
        print("\nNo new data available. Sheet is up to date.")
        return

    print("\nDaily update complete!")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
