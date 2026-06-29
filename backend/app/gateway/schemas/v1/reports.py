"""Report and ReportSpec DTOs for v1 external API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# ReportSpec — intermediate structured report format
# ---------------------------------------------------------------------------

ContentBlockType = Literal["paragraph", "bullets", "numbered_list", "table", "code", "heading", "quote", "image"]


class TableContent(BaseModel):
    """Table content block."""

    columns: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class ContentBlock(BaseModel):
    """A single content block within a report section."""

    type: ContentBlockType = Field(description="Block type")
    text: str | None = Field(default=None, description="Text content (for paragraph, heading, quote)")
    items: list[str] | None = Field(default=None, description="List items (for bullets, numbered_list)")
    table: TableContent | None = Field(default=None, description="Table data (for table)")
    code: str | None = Field(default=None, description="Code content (for code)")
    language: str | None = Field(default=None, description="Code language")
    level: int | None = Field(default=None, description="Heading level (1-6)")
    image_url: str | None = Field(default=None, description="Image URL (for image)")
    image_alt: str | None = Field(default=None, description="Image alt text")


class Citation(BaseModel):
    """A citation/source reference."""

    id: str = Field(description="Citation ID, e.g. src_001")
    label: str = Field(description="Display label")
    source_type: str = Field(default="datasource", description="Source type: datasource, conversation, url")
    locator: str | None = Field(default=None, description="Specific location within source")


class ReportSection(BaseModel):
    """A single section within a report."""

    heading: str = Field(description="Section heading/title")
    content: list[ContentBlock] = Field(default_factory=list, description="Content blocks")


class ReportSpec(BaseModel):
    """Intermediate structured report format.

    The report-agent outputs this format. Renderers (DOCX, HTML, PDF)
    consume this format to produce final artifacts.
    """

    title: str = Field(description="Report title")
    subtitle: str | None = Field(default=None, description="Report subtitle")
    metadata: dict[str, Any] = Field(
        default_factory=lambda: {
            "author": "intelli-engine",
            "language": "zh-CN",
            "generated_at": None,
        },
    )
    sections: list[ReportSection] = Field(default_factory=list, description="Report sections")
    citations: list[Citation] = Field(default_factory=list, description="Citation list")


# ---------------------------------------------------------------------------
# Report generation request / response
# ---------------------------------------------------------------------------

ReportType = Literal["analysis", "summary", "research", "meeting_notes", "decision_memo"]
ReportFormat = Literal["docx", "pdf", "html"]


class ReportCreateRequest(BaseModel):
    """Request to generate a report."""

    title: str = Field(description="Report title")
    format: list[ReportFormat] = Field(default=["docx", "html"], description="Output formats")
    report_type: ReportType = Field(default="analysis", description="Report type")
    datasource_ids: list[str] = Field(default_factory=list, description="Data source IDs to include")
    user_query: str | None = Field(default=None, description="Natural language query for SQL/ES data sources. Used to trigger Text-to-SQL/ES queries before report generation.")
    include_conversation: bool = Field(default=True, description="Include conversation QA in report")
    include_citations: bool = Field(default=True, description="Include citations")
    language: str = Field(default="zh-CN", description="Report language")
    style: str = Field(default="business", description="Report style")
    sections: list[str] | None = Field(default=None, description="Custom section list (overrides defaults)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional metadata")


class ReportArtifact(BaseModel):
    """A report output artifact."""

    artifact_id: str = Field(description="Artifact ID for download")
    format: str = Field(description="File format: docx, pdf, html")
    filename: str = Field(description="File name")
    url: str = Field(description="Download URL")


class ReportResponse(BaseModel):
    """Response for report creation (async)."""

    report_id: str = Field(description="Unique report ID")
    conversation_id: str = Field(description="Parent conversation ID")
    status: str = Field(default="queued", description="Status: queued, processing, success, failed")
    created_at: str = Field(default="", description="ISO timestamp")


class ReportStatusResponse(BaseModel):
    """Full report status including artifacts on completion."""

    report_id: str
    conversation_id: str
    status: str
    title: str = ""
    summary: str = ""
    artifacts: list[ReportArtifact] = Field(default_factory=list)
    error: str | None = None
    created_at: str = ""
    updated_at: str = ""
    usage: dict[str, int] | None = None
