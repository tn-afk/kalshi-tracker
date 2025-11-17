#!/usr/bin/env python3
"""
Kalshi Volume Tracker Web Service
Runs daily at 12pm UK time to update Google Sheet
"""
import os
import threading
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from daily_update import main as run_daily_update

app = Flask(__name__)

# Track last run status
last_run_status = {
    'status': 'never_run',
    'timestamp': None,
    'message': None
}

def scheduled_task():
    """Run the daily update task"""
    global last_run_status
    from datetime import datetime

    try:
        print(f"Starting scheduled update at {datetime.now()}", flush=True)
        last_run_status = {
            'status': 'running',
            'timestamp': datetime.now().isoformat(),
            'message': 'Update in progress'
        }

        run_daily_update()

        last_run_status = {
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'message': 'Update completed successfully'
        }
        print(f"Scheduled update completed at {datetime.now()}", flush=True)
    except Exception as e:
        last_run_status = {
            'status': 'error',
            'timestamp': datetime.now().isoformat(),
            'message': str(e)
        }
        print(f"Error in scheduled update: {e}", flush=True)

@app.route('/')
@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Kalshi Volume Tracker',
        'last_run': last_run_status
    })

@app.route('/trigger')
def trigger():
    """Manual trigger endpoint"""
    thread = threading.Thread(target=scheduled_task)
    thread.start()
    return jsonify({
        'status': 'triggered',
        'message': 'Update started in background'
    })

@app.route('/status')
def status():
    """Status endpoint"""
    return jsonify(last_run_status)

def init_scheduler():
    """Initialize the background scheduler"""
    scheduler = BackgroundScheduler()

    # Schedule for 12pm UK time (Europe/London timezone)
    uk_tz = pytz.timezone('Europe/London')
    trigger = CronTrigger(hour=12, minute=0, timezone=uk_tz)

    scheduler.add_job(
        func=scheduled_task,
        trigger=trigger,
        id='daily_kalshi_update',
        name='Daily Kalshi Update',
        replace_existing=True
    )

    scheduler.start()
    print("Scheduler initialized - will run daily at 12pm UK time", flush=True)

    # Run immediately on startup to catch up on missed days
    print("Running initial update to catch up on missed days...", flush=True)
    thread = threading.Thread(target=scheduled_task)
    thread.start()

if __name__ == '__main__':
    init_scheduler()
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
