#!/usr/bin/env python3
"""
Optimized Kalshi Daily Data Updater
Fast, efficient data collection with better download performance
"""
import json
import os
import sys
from datetime import datetime, timedelta
import requests
from google.oauth2.credentials import Credentials

# Configuration
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', '1HzPlGwvV9G0mMTEUibI_8WecxgWwK-zfCNr0tGS-q2I')
GOOGLE_REFRESH_TOKEN = os.getenv('GOOGLE_REFRESH_TOKEN')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
MAJOR_US_SPORTS = ['NBA', 'NFL', 'NCAA', 'MLB', 'MLS', 'NHL']

def get_access_token():
    """Get fresh Google OAuth access token"""
    creds = Credentials(
        token=None,
        refresh_token=GOOGLE_REFRESH_TOKEN,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET
    )
    from google.auth.transport.requests import Request
    creds.refresh(Request())
    return creds.token

def download_and_process(date_str):
    """Download and process Kalshi data with optimized chunking"""
    url = f"https://kalshi-public-docs.s3.amazonaws.com/reporting/market_data_{date_str}.json"

    print(f"[{date_str}] Fetching data...", flush=True)

    try:
        # Use larger chunks and aggressive timeout
        response = requests.get(url, timeout=180, stream=True)

        if response.status_code != 200:
            print(f"[{date_str}] Not available (HTTP {response.status_code})", flush=True)
            return None

        # Download with 1MB chunks (much faster than 8KB)
        chunks = []
        for chunk in response.iter_content(chunk_size=1048576):
            if chunk:
                chunks.append(chunk)

        data = json.loads(b''.join(chunks))

        # Process incrementally
        total = major_sports = kxmve = 0
        for record in data:
            vol = record.get('daily_volume', 0)
            total += vol

            ticker = record.get('ticker_name', '')
            if any(sport in ticker for sport in MAJOR_US_SPORTS):
                major_sports += vol
            if 'KXMVE' in ticker:
                kxmve += vol

        print(f"[{date_str}] ✓ Volume: {total:,}", flush=True)

        return {
            'date': date_str,
            'total_volume': total,
            'major_sports_volume': major_sports,
            'kxmve_volume': kxmve
        }

    except Exception as e:
        print(f"[{date_str}] Error: {e}", flush=True)
        return None

def update_sheet(token, rows):
    """Append rows to Google Sheet"""
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/Kalshi Data!A:D'
    headers = {'Authorization': f'Bearer {token}'}

    # Get next row
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    next_row = len(resp.json().get('values', [])) + 1

    # Append
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/Kalshi Data!A{next_row}:append'
    resp = requests.post(
        url,
        headers=headers,
        json={'values': rows},
        params={'valueInputOption': 'RAW'}
    )
    resp.raise_for_status()
    print(f"✓ Added {len(rows)} row(s) to sheet", flush=True)

def main():
    print(f"=== Kalshi Tracker - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n", flush=True)

    # Get latest date from sheet
    token = get_access_token()
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/Kalshi Data!A:A'
    resp = requests.get(url, headers={'Authorization': f'Bearer {token}'})
    resp.raise_for_status()

    dates = resp.json().get('values', [])
    if len(dates) > 1:
        latest = datetime.strptime(dates[-1][0], '%Y-%m-%d')
    else:
        latest = datetime(2025, 11, 13)

    print(f"Latest in sheet: {latest.strftime('%Y-%m-%d')}\n", flush=True)

    # Check up to 10 days ahead
    results = []
    for i in range(1, 11):
        check_date = latest + timedelta(days=i)
        if check_date > datetime.now():
            break

        result = download_and_process(check_date.strftime('%Y-%m-%d'))
        if result:
            results.append(result)

    if not results:
        print("\n✓ Sheet is up to date", flush=True)
        return

    # Update sheet
    print(f"\nUpdating sheet with {len(results)} day(s)...", flush=True)
    rows = [[r['date'], r['total_volume'], r['major_sports_volume'], r['kxmve_volume']] for r in results]
    update_sheet(get_access_token(), rows)

    print("\n✓ Complete!", flush=True)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
