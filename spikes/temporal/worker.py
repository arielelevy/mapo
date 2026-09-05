"""Worker del spike. `python worker.py` y listo. El demo lo levanta y lo mata."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import timedelta

from temporalio.client import Client
from temporalio.worker import Worker

import activities
import workflows
from shared import TASK_QUEUE

ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")


async def main() -> None:
    client = await Client.connect(ADDRESS)
    # Los workflow tasks van primero a la cola sticky del último worker. Si ese worker
    # murió, el server espera este timeout (default 10s) antes de mandarlo a la cola
    # general. Bajarlo es lo que hace rápida la reanudación tras una caída.
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=workflows.ALL,
        activities=activities.ALL,
        sticky_queue_schedule_to_start_timeout=timedelta(seconds=2),
    )
    print(f"worker pid={os.getpid()} queue={TASK_QUEUE} address={ADDRESS}", flush=True)
    await worker.run()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
