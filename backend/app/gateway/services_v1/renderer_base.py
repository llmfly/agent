"""Base renderer interface and shared utilities."""

from __future__ import annotations

from app.gateway.schemas.v1.reports import ReportSpec


class BaseRenderer:
    """Base class for report renderers."""

    def render(self, spec: ReportSpec) -> bytes:
        """Render a ReportSpec into the target format.

        Args:
            spec: The ReportSpec to render.

        Returns:
            The rendered document as bytes.
        """
        raise NotImplementedError

    @property
    def mime_type(self) -> str:
        """Return the MIME type of the rendered output."""
        raise NotImplementedError

    @property
    def file_extension(self) -> str:
        """Return the file extension (without leading dot)."""
        raise NotImplementedError
