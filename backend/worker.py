"""Production entrypoint for the durable music-processing worker."""

import logging
import os
import signal

from domain.capabilities import register_all_capabilities
from domain.job_worker import JobWorker


def _init_sentry() -> None:
    dsn = os.environ.get("SENTRY_DSN_BACKEND") or os.environ.get("SENTRY_DSN")
    if not dsn:
        return
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=os.environ.get("SENTRY_ENV", "production"),
            release=os.environ.get("RELEASE", "development"),
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            send_default_pii=False,
        )
    except ImportError:
        logging.getLogger("worker").warning("sentry_sdk_not_installed")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    _init_sentry()
    worker = JobWorker(max_workers=int(os.environ.get("WORKER_CONCURRENCY", "1")))
    register_all_capabilities(worker)

    def stop(_signum, _frame) -> None:
        worker.stop()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    worker.run()


if __name__ == "__main__":
    main()
