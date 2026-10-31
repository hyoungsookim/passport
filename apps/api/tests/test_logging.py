import logging

from passport.core.logging import queue_logging


def test_queue_logging_flushes_pending_records_on_exit(capsys):
    root_handlers = list(logging.getLogger().handlers)

    with queue_logging():
        logging.getLogger("passport.test").info("hello")
        logging.getLogger("sqlalchemy.engine").info("SELECT secret")

    err = capsys.readouterr().err
    assert "INFO [passport.test] hello" in err
    assert "SELECT secret" not in err
    assert logging.getLogger().handlers == root_handlers
