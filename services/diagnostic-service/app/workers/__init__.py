"""Workers."""

from app.workers.consumer_worker import SqsDiagnosticWorker

__all__ = ["SqsDiagnosticWorker"]
