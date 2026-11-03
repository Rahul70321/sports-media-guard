"""Durable schedule loop for monitoring targets."""

import time

from services.scan_orchestrator import claim_due_runs, execute_run


def main():
    print("Sports Media Guard scheduler started", flush=True)
    while True:
        run_ids = claim_due_runs()
        for run_id in run_ids:
            execute_run(run_id)
        time.sleep(30)


if __name__ == "__main__":
    main()
