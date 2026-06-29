"""Gateway-level tools that the Lead Agent can use.

These tools are registered in config.yaml under the ``tools:`` section.
They have access to Gateway services (data source, report, etc.) but not to
harness internals (harness never imports app).
"""

from app.gateway.tools.doc_parser import extract_pdf_metadata, parse_docx, parse_pdf
from app.gateway.tools.report_tool import check_report_status, generate_report

__all__ = [
    "generate_report",
    "check_report_status",
    "parse_pdf",
    "parse_docx",
    "extract_pdf_metadata",
]
