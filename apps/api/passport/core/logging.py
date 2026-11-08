"""Non-blocking logging: records are queued and written by a background thread."""

import logging
import queue
from collections.abc import Generator
from contextlib import contextmanager
from logging.handlers import QueueHandler, QueueListener


@contextmanager
def queue_logging() -> Generator[None]:
    log_queue: queue.SimpleQueue[logging.LogRecord] = queue.SimpleQueue()
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    listener = QueueListener(log_queue, stream_handler)
    queue_handler = QueueHandler(log_queue)
    root = logging.getLogger()
    root.addHandler(queue_handler)
    # Only our loggers go to INFO; root stays at WARNING so sqlalchemy.engine
    # does not start logging every SQL statement.
    logging.getLogger("passport").setLevel(logging.INFO)
    listener.start()
    try:
        yield
    finally:
        root.removeHandler(queue_handler)
        listener.stop()  # drains records still in the queue
