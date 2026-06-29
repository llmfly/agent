"""HTML report renderer.

Converts a ReportSpec into a self-contained HTML document with
inline CSS styling. The output is a single HTML file with no
external dependencies.
"""

from __future__ import annotations

import html as html_mod
from datetime import datetime

from app.gateway.schemas.v1.reports import ContentBlock, ReportSection, ReportSpec, TableContent
from app.gateway.services_v1.renderer_base import BaseRenderer


class HtmlRenderer(BaseRenderer):
    """Render ReportSpec to a self-contained HTML document."""

    @property
    def mime_type(self) -> str:
        return "text/html"

    @property
    def file_extension(self) -> str:
        return "html"

    def render(self, spec: ReportSpec) -> bytes:
        """Render ReportSpec to HTML."""
        html_content = self._build_html(spec)
        return html_content.encode("utf-8")

    def _build_html(self, spec: ReportSpec) -> str:
        """Build the full HTML document."""
        sections_html = "\n".join(self._render_section(s) for s in spec.sections)
        citations_html = self._render_citations(spec.citations) if spec.citations else ""

        now = datetime.now().isoformat()

        return f"""<!DOCTYPE html>
<html lang="{spec.metadata.get('language', 'zh-CN')}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_mod.escape(spec.title)}</title>
<style>
  {self._css_styles()}
</style>
</head>
<body>
  <div class="report-container">
    <header class="report-header">
      <h1 class="report-title">{html_mod.escape(spec.title)}</h1>
      {f'<p class="report-subtitle">{html_mod.escape(spec.subtitle)}</p>' if spec.subtitle else ''}
      <div class="report-meta">
        <span>作者: {html_mod.escape(str(spec.metadata.get('author', 'intelli-engine')))}</span>
        <span>生成时间: {now}</span>
      </div>
    </header>

    <nav class="toc">
      <h2>目录</h2>
      <ul>
        {''.join(f'<li><a href="#section-{i}">{html_mod.escape(s.heading)}</a></li>' for i, s in enumerate(spec.sections))}
      </ul>
    </nav>

    <main class="report-body">
      {sections_html}
    </main>

    {citations_html}

    <footer class="report-footer">
      <p>由 intelli-engine AI 能力平台生成 | {now}</p>
    </footer>
  </div>
</body>
</html>"""

    def _render_section(self, section: ReportSection, index: int | None = None) -> str:
        """Render a single report section."""
        section_id = f"section-{index}" if index is not None else ""
        heading_tag = f"h{min(section.content[0].level if section.content and section.content[0].level else 2, 6)}" if section.content and section.content[0].type == "heading" else "h2"

        blocks_html = "\n".join(self._render_block(b) for b in section.content)
        return f"""
    <section id="{section_id}" class="report-section">
      <{heading_tag} class="section-heading">{html_mod.escape(section.heading)}</{heading_tag}>
      {blocks_html}
    </section>"""

    def _render_block(self, block: ContentBlock) -> str:
        """Render a single content block."""
        if block.type == "paragraph" and block.text:
            return f'<p class="paragraph">{self._render_inline(block.text)}</p>'

        elif block.type == "heading":
            level = min(block.level or 2, 6)
            text = html_mod.escape(block.text or "")
            return f'<h{level} class="section-heading">{text}</h{level}>'

        elif block.type == "bullets" and block.items:
            items = "".join(f"<li>{self._render_inline(item)}</li>" for item in block.items)
            return f'<ul class="bullet-list">{items}</ul>'

        elif block.type == "numbered_list" and block.items:
            items = "".join(f"<li>{self._render_inline(item)}</li>" for item in block.items)
            return f'<ol class="numbered-list">{items}</ol>'

        elif block.type == "table" and block.table:
            return self._render_table(block.table)

        elif block.type == "code" and block.code:
            lang = html_mod.escape(block.language or "")
            code = html_mod.escape(block.code)
            return f'<pre class="code-block"><code class="language-{lang}">{code}</code></pre>'

        elif block.type == "quote" and block.text:
            return f'<blockquote class="quote">{self._render_inline(block.text)}</blockquote>'

        elif block.type == "image":
            src = html_mod.escape(block.image_url or "")
            alt = html_mod.escape(block.image_alt or "")
            return f'<figure class="image-figure"><img src="{src}" alt="{alt}" /><figcaption>{alt}</figcaption></figure>'

        return ""

    def _render_table(self, table: TableContent) -> str:
        """Render a table block."""
        header = ""
        if table.columns:
            header = "<thead><tr>" + "".join(f"<th>{html_mod.escape(c)}</th>" for c in table.columns) + "</tr></thead>"

        body = ""
        if table.rows:
            body = "<tbody>" + "".join(
                "<tr>" + "".join(f"<td>{self._render_inline(cell)}</td>" for cell in row) + "</tr>"
                for row in table.rows
            ) + "</tbody>"

        return f'<div class="table-wrapper"><table class="data-table">{header}{body}</table></div>'

    def _render_inline(self, text: str) -> str:
        """Render inline text with basic markdown-like formatting."""
        text = html_mod.escape(text)
        # Bold
        text = text.replace("**", "<strong>", 1)
        # Simple inline formatting - this is basic, could be enhanced
        return text

    def _render_citations(self, citations: list) -> str:
        """Render the citations section."""
        if not citations:
            return ""
        items = "".join(
            f'<li id="cit-{c.id}">[{c.id}] {html_mod.escape(c.label)}'
            + (f' — <em>{html_mod.escape(c.locator)}</em>' if c.locator else "")
            + "</li>"
            for c in citations
        )
        return f"""
    <section class="citations-section">
      <h2>参考资料</h2>
      <ol class="citation-list">{items}</ol>
    </section>"""

    @staticmethod
    def _css_styles() -> str:
        """Return the embedded CSS styles."""
        return """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: #1a1a2e;
  background: #f5f5f5;
  line-height: 1.8;
  font-size: 14px;
}
.report-container {
  max-width: 900px;
  margin: 0 auto;
  background: #ffffff;
  box-shadow: 0 0 20px rgba(0,0,0,0.08);
  min-height: 100vh;
  padding: 60px 80px;
}
.report-header {
  text-align: center;
  padding-bottom: 40px;
  border-bottom: 2px solid #e8e8e8;
  margin-bottom: 40px;
}
.report-title {
  font-size: 28px;
  font-weight: 700;
  color: #1a1a2e;
  margin-bottom: 8px;
}
.report-subtitle {
  font-size: 16px;
  color: #666;
  margin-bottom: 16px;
}
.report-meta {
  font-size: 12px;
  color: #999;
  display: flex;
  gap: 20px;
  justify-content: center;
}
.toc {
  background: #f8f9fa;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 24px 32px;
  margin-bottom: 40px;
}
.toc h2 {
  font-size: 18px;
  margin-bottom: 12px;
  color: #1a1a2e;
}
.toc ul { list-style: none; }
.toc li { margin-bottom: 6px; }
.toc a {
  color: #2563eb;
  text-decoration: none;
  font-size: 14px;
}
.toc a:hover { text-decoration: underline; }
.report-section {
  margin-bottom: 40px;
}
.section-heading {
  font-size: 22px;
  font-weight: 600;
  color: #1a1a2e;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e8e8e8;
}
.paragraph {
  margin-bottom: 12px;
  text-align: justify;
}
.bullet-list, .numbered-list {
  margin: 12px 0;
  padding-left: 24px;
}
.bullet-list li, .numbered-list li {
  margin-bottom: 6px;
}
.table-wrapper {
  overflow-x: auto;
  margin: 16px 0;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.data-table th, .data-table td {
  border: 1px solid #ddd;
  padding: 10px 12px;
  text-align: left;
}
.data-table th {
  background: #f0f4ff;
  font-weight: 600;
  color: #1a1a2e;
}
.data-table tr:nth-child(even) { background: #fafafa; }
.code-block {
  background: #1e1e2e;
  color: #cdd6f4;
  border-radius: 8px;
  padding: 16px 20px;
  overflow-x: auto;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  margin: 16px 0;
}
.quote {
  border-left: 4px solid #2563eb;
  padding: 12px 20px;
  margin: 16px 0;
  background: #f8f9fa;
  color: #555;
  font-style: italic;
  border-radius: 0 8px 8px 0;
}
.image-figure {
  margin: 20px 0;
  text-align: center;
}
.image-figure img {
  max-width: 100%;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
.image-figure figcaption {
  margin-top: 8px;
  font-size: 12px;
  color: #888;
}
.citations-section {
  margin-top: 60px;
  padding-top: 32px;
  border-top: 2px solid #e8e8e8;
}
.citations-section h2 {
  font-size: 20px;
  margin-bottom: 16px;
}
.citation-list {
  padding-left: 24px;
  font-size: 13px;
  color: #666;
}
.citation-list li {
  margin-bottom: 8px;
  word-break: break-all;
}
.report-footer {
  margin-top: 60px;
  padding-top: 20px;
  border-top: 1px solid #e8e8e8;
  text-align: center;
  font-size: 12px;
  color: #aaa;
}
@media print {
  body { background: white; }
  .report-container { box-shadow: none; padding: 40px; }
  .toc { break-after: page; }
  .report-section { break-inside: avoid-page; }
}
"""
