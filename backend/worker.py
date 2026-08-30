"""Production entrypoint for the durable music-processing worker."""

import logging
import os
import signal

import domain.capabilities as capability_module
from domain.correction_entity_sync import register_corrected_midi_entity_sync
from domain.job_worker import JobWorker
from domain.perceptual_capability import register_perceptual_capability
from domain.performance_instrumentation import install_understand_instrumentation
from domain.worker_warmup import (
    prewarm_basic_pitch_inference,
    prewarm_beat_this_inference,
    prewarm_librosa_beat_tracking,
)
from observability import configure_logging, init_sentry, init_telemetry


def main() -> None:
    configure_logging("hello-ai-worker")
    logger = logging.getLogger("worker")
    init_telemetry("hello-ai-worker")
    init_sentry(logger)

    # Pay expensive process-local cold paths before JobWorker.run() publishes
    # its first heartbeat or claims a user's job. Warmups are optimization-only:
    # one failure must not prevent worker startup. Exactly one beat-engine warmup
    # runs for the configured engine; Beat This is the production default and
    # librosa remains an explicit rollback path.
    try:
        prewarm_basic_pitch_inference()
    except Exception:
        logger.exception("basic_pitch_prewarm_failed")

    try:
        prewarm_beat_this_inference()
    except Exception:
        logger.exception("beat_this_prewarm_failed")

    try:
        prewarm_librosa_beat_tracking()
    except Exception:
        logger.exception("librosa_beat_prewarm_failed")

    worker = JobWorker(max_workers=int(os.environ.get("WORKER_CONCURRENCY", "1")))
    install_understand_instrumentation(capability_module)
    capability_module.register_all_capabilities(worker)
    register_corrected_midi_entity_sync(worker)
    register_perceptual_capability(worker)

    def stop(_signum, _frame) -> None:
        worker.stop()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    worker.run()


if __name__ == "__main__":
    main()
