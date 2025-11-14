# Kalshi Volume Tracker

Automated daily tracker for Kalshi market volume data. Runs as a Render cron job to update a Google Sheet daily at 12pm EST.

## What it does

- Checks for new Kalshi market data daily
- Calculates three metrics:
  - Total volume
  - Major US Sports volume (NBA, NFL, NCAA, MLB, MLS, NHL)
  - KXMVE volume
- Appends new data to Google Sheet

## Deployment

Deployed on Render as a cron job. Environment variables required:

- `SPREADSHEET_ID` - Google Sheet ID
- `GOOGLE_ACCESS_TOKEN` - Google OAuth access token
- `GOOGLE_REFRESH_TOKEN` - Google OAuth refresh token
- `GOOGLE_CLIENT_ID` - Google OAuth client ID
- `GOOGLE_CLIENT_SECRET` - Google OAuth client secret

## Data Source

- Kalshi Public Data: `https://kalshi-public-docs.s3.amazonaws.com/reporting/`
- Format: `market_data_YYYY-MM-DD.json`

## Google Sheet

https://docs.google.com/spreadsheets/d/1HzPlGwvV9G0mMTEUibI_8WecxgWwK-zfCNr0tGS-q2I/edit
