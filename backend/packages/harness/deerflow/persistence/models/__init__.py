"""ORM model registration entry point.

Importing this module ensures all ORM models are registered with
``Base.metadata`` so Alembic autogenerate detects every table.

The actual ORM classes have moved to entity-specific subpackages:
- ``deerflow.persistence.thread_meta``
- ``deerflow.persistence.run``
- ``deerflow.persistence.feedback``
- ``deerflow.persistence.user``
- ``deerflow.persistence.datasource``

``RunEventRow`` remains in ``deerflow.persistence.models.run_event`` because
its storage implementation lives in ``deerflow.runtime.events.store.db`` and
there is no matching entity directory.
"""

from deerflow.persistence.datasource.model import ConversationDataSourceRow, DataSourceRow
from deerflow.persistence.feedback.model import FeedbackRow
from deerflow.persistence.models.run_event import RunEventRow
from deerflow.persistence.run.model import RunRow
from deerflow.persistence.thread_meta.model import ThreadMetaRow
from deerflow.persistence.user.model import UserRow
from deerflow.persistence.models.artifact import ArtifactRow, ArtifactFileRow

__all__ = [
    "ConversationDataSourceRow",
    "DataSourceRow",
    "FeedbackRow",
    "RunEventRow",
    "RunRow",
    "ThreadMetaRow",
    "UserRow",
    "ArtifactRow",
    "ArtifactFileRow",
]
