import time
import schedule
from etl_pipeline import run_full_pipeline

# Interval setting (in minutes)
INTERVAL_MINUTES = 15

def job():
    print(f"\n[SCHEDULER] Triggering ETL Pipeline update...")
    try:
        run_full_pipeline()
    except Exception as e:
        print(f"[SCHEDULER ERROR] Pipeline run failed: {e}")

if __name__ == "__main__":
    print(f"==================================================")
    print(f"EVACASSIST AUTOMATED SCHEDULER STARTED")
    print(f"Running pipeline every {INTERVAL_MINUTES} minutes.")
    print(f"Press Ctrl+C to stop.")
    print(f"==================================================")

    # 1. Run once immediately on startup
    job()

    # 2. Schedule recurring executions
    schedule.every(INTERVAL_MINUTES).minutes.do(job)

    # 3. Keep script running
    while True:
        schedule.run_pending()
        time.sleep(1)