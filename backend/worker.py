"""Production entrypoint for the durable music-processing worker."""

import logging
import signal

from domain.capabilities import register_all_capabilities
from domain.job_worker import JobWorker


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    worker = JobWorker()
    register_all_capabilities(worker)

    def stop(_signum, _frame) -> None:
        worker.stop()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    worker.run()


if __name__ == "__main__":
    main()
