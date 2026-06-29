"""Worker implementations for the Execution Layer.

Each Worker is stateless, registered via CapabilityRegistry, and
returns List[Evidence] for every execute() call.
"""

from .base import BaseWorker, ExecutionDAG, ExecutionTask
from .doc_worker import DocxWorker, PdfMetadataWorker, PdfWorker

__all__ = [
    "BaseWorker",
    "ExecutionTask",
    "ExecutionDAG",
    "PdfWorker",
    "DocxWorker",
    "PdfMetadataWorker",
]


def register_doc_workers() -> list[BaseWorker]:
    """Create and return document parsing workers for registration."""
    return [PdfWorker(), DocxWorker(), PdfMetadataWorker()]
