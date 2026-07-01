"""Run adapter — builds ``RunCreateRequest`` from ``ConversationMessageRequest``.

This module provides the backward-compatible ``build_run_create_request``
entrypoint.  Internally it delegates to the ``ContextBuilder`` chain
(:mod:`app.gateway.services_v1.context_builder`).

The old helper functions (``_detect_report_intent``, ``_format_data_sources_for_prompt``,
``_build_datasource_system_message``, ``_NO_SOURCE_INSTRUCTIONS``) have been moved to:

- :mod:`app.gateway.services_v1.context_builder`
- :mod:`app.gateway.routing.intent_classifier`
"""

from __future__ import annotations

import logging
from typing import Any

from app.gateway.routers.thread_runs import RunCreateRequest
from app.gateway.schemas.v1.conversations import ConversationMessageRequest
from app.gateway.services_v1.context_builder import ContextBuilder
from app.gateway.services_v1.external_context import ExternalContext

logger = logging.getLogger(__name__)

# Module-level singleton — built once, reused across calls.
_context_builder = ContextBuilder()


def build_run_create_request(
    body: ConversationMessageRequest,
    external_context: ExternalContext,
    *,
    selected_data_sources: list[dict[str, Any]] | None = None,
) -> RunCreateRequest:
    """Build a ``RunCreateRequest`` from a conversation message request.

    Parameters, return value and behaviour are identical to the V1
    implementation.  The internal implementation delegates to the
    ``ContextBuilder`` chain for modularity.

    Args:
        body: The incoming conversation message request.
        external_context: Auth / external user context.
        selected_data_sources: Optional list of attached data source schemas.

    Returns:
        A ``RunCreateRequest`` ready for submission to the LangGraph runtime.
    """
    return _context_builder.build(
        body=body,
        external_context=external_context,
        selected_data_sources=selected_data_sources,
    )
