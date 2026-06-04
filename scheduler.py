import time
import sys
import argparse
from sync_hivemind import sync_from_hivemind

def run_scheduler(interval_seconds):
    print(f"\n======================================================================")
    print(f"[*] AIN STATE COMPILER SCHEDULER STARTING")
    print(f"--> Ingestion Interval: {interval_seconds} seconds")
    print(f"--> Mode: 100% Offline | Zero-LLM Inflow Ingestion")
    print(f"======================================================================\n")
    
    try:
        while True:
            t_start = time.time()
            success = sync_from_hivemind()
            if success:
                print(f"[SUCCESS] State synchronized and compiled at {time.strftime('%Y-%m-%d %H:%M:%S')}.")
            else:
                print(f"[ERROR] Sync failure at {time.strftime('%Y-%m-%d %H:%M:%S')}.")
                
            # Print next sleep interval
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\n[*] Scheduler daemon stopped by user.")
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AIN 5-Minute Sync Scheduler")
    parser.add_argument("--interval", type=int, default=300, help="Interval in seconds (default: 300/5-mins)")
    args = parser.parse_args()
    
    run_scheduler(args.interval)
