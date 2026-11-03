"""Durable monitoring worker."""

import time

from services.scan_orchestrator import claim_due_runs, execute_run


def main():
    print("Sports Media Guard worker started", flush=True)
    while True:
        run_ids = claim_due_runs()
        for run_id in run_ids:
            execute_run(run_id)
        time.sleep(5)


if __name__ == "__main__":
    main()
