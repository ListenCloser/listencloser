"""Production entrypoint for the durable music-processing worker."""

import logging
import os
import signal

import domain.capabilities as capability_module
from domain.job_worker import JobWorker
from domain.perceptual_capability import register_perceptual_capability
from domain.performance_instrumentation import install_understand_instrumentation
from observability import configure_logging, init_sentry, init_telemetry


def main() -> None:
    configure_logging("hello-ai-worker")
    logger = logging.getLogger("worker")
    init_telemetry("hello-ai-worker")
    init_sentry(logger)
    worker = JobWorker(max_workers=int(os.environ.get("WORKER_CONCURRENCY", "1")))
    install_understand_instrumentation(capability_module)
    capability_module.register_all_capabilities(worker)
    register_perceptual_capability(worker)

    def stop(_signum, _frame) -> None:
        worker.stop()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    worker.run()


if __name__ == "__main__":
    main()
