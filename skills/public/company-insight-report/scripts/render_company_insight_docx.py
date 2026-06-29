#!/usr/bin/env python3
"""Render a company insight report as a .docx file using only Python stdlib."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
SAMPLE_DIR = SKILL_DIR / "assets" / "sample"
DEFAULT_TEMPLATE = SKILL_DIR / "assets" / "word_template.json"

SECTION_ORDER = [
    "1 企业贸易全景概览",
    "1.1 核心出口产品",
    "1.1.1 核心出口产品识别",
    "1.1.2 产品销售贡献分析",
    "1.1.3 产品结构变化趋势",
    "1.2 覆盖市场分布",
    "1.3 整体出口体量",
    "2 既有市场表现评估",
    "2.1 各市场出货表现",
    "2.2 增长趋势分析",
    "2.3 市场健康度",
    "3 竞争格局与自身定位",
    "3.1 市场竞争总览",
    "3.2 竞争对手排行",
    "3.3 价格竞争分析",
    "3.4 自身定位总结",
    "4 空白市场机会与买家挖掘",
    "4.1 空白市场识别与排序",
    "4.2 TOP买家挖掘",
    "4.3 切入评估",
    "5 总结与建议",
    "5.1 核心结论",
    "5.2 风险提示",
    "5.3 战略建议",
]

STRUCTURAL_ONLY_SECTIONS = {"1.1 核心出口产品"}

SECTION_ALIASES = {
    "1.1.1 核心出口产品识别": ["1.1 核心出口产品识别"],
}

TABLE_TITLES = {
    "product_table": "核心出口产品一览",
    "country_table": "出口目的国分布",
    "market_performance": "既有市场出货表现",
    "market_health": "市场健康度指标",
    "rival_table": "主要竞争对手一览",
    "ranked_opportunities": "空白市场机会排序",
    "top_buyers": "目标市场主要进口商",
    "core_findings": "核心发现",
    "risks": "风险提示",
    "recommendations": "战略建议"
}

TABLE_COLUMNS = {
    "product_table": [("hs", "HS编码"), ("desc", "产品描述"), ("amount", "金额"), ("share", "占比"), ("txn_count", "该产品交易笔数")],
    "country_table": [("country", "目的国"), ("amount", "金额"), ("share", "占比"), ("customer_count", "客户数")],
    "market_performance": [("country", "目的国"), ("amount", "金额"), ("share", "占比"), ("avg_price", "均价"), ("customer_count", "客户数"), ("growth", "增速")],
    "market_health": [("country", "目的国"), ("top1_customer_share", "Top1客户占比"), ("avg_monthly_txn", "月均交易"), ("price_std", "价格波动"), ("reorder_rate", "复购率")],
    "rival_table": [("supplier", "供应商"), ("supplier_country", "国家"), ("amount", "金额"), ("share", "份额"), ("avg_price", "均价"), ("customer_count", "客户数")],
    "ranked_opportunities": [("country", "目的国"), ("total_amount", "行业规模"), ("supplier_count", "供应商数"), ("opportunity_score", "机会评分"), ("priority", "优先级")],
    "top_buyers": [("buyer", "采购商"), ("amount", "采购总额"), ("avg_price", "均价"), ("supplier_count", "供应商数"), ("price_gap_vs_target", "与目标企业价差")],
}

FIELD_ALIASES = {
    "hs": ["hs", "HS Code", "HS编码", "hs_code"],
    "desc": ["desc_zh", "产品描述中文", "中文产品描述", "商品描述中文", "desc", "产品描述", "商品描述"],
    "amount": ["amount", "金额", "金额美元", "总价", "采购总额"],
    "share": ["share", "占比", "percentage", "份额"],
    "txn_count": ["txn_count", "交易笔数", "数量", "quantity"],
    "country": ["country", "出口国家", "目的国/地区", "目的国", "国家"],
    "customer_count": ["customer_count", "客户数", "buyer_count", "采购商数"],
    "avg_price": ["avg_price", "均价", "average_price", "unit_price"],
    "growth": ["growth", "增速"],
    "top1_customer_share": ["top1_customer_share", "Top1客户占比"],
    "avg_monthly_txn": ["avg_monthly_txn", "月均交易"],
    "price_std": ["price_std", "价格波动"],
    "reorder_rate": ["reorder_rate", "复购率"],
    "supplier": ["supplier", "供应商"],
    "supplier_country": ["supplier_country", "供应商国家", "国家"],
    "supplier_count": ["supplier_count", "供应商数", "supplier_num"],
    "total_amount": ["total_amount", "行业规模", "金额美元", "金额"],
    "opportunity_score": ["opportunity_score", "机会评分"],
    "priority": ["priority", "优先级"],
    "buyer": ["buyer", "采购商", "买家", "进口商"],
    "price_gap_vs_target": ["price_gap_vs_target", "与目标企业价差", "price_gap"],
}

MISSING_DISPLAY_KEYS = {"avg_price", "customer_count", "supplier_count", "price_gap_vs_target"}

HS_CODE_DESCRIPTIONS = {
    "850760": "锂离子蓄电池",
    "870322": "汽油乘用车",
    "870380": "新能源汽车",
    "870829": "车身及附件",
    "870899": "机动车零部件",
}

SECTION_TABLES_AFTER = {
    "1.1.1 核心出口产品识别": ["product_table"],
    "1.2 覆盖市场分布": ["country_table"],
    "2.1 各市场出货表现": ["market_performance"],
    "2.3 市场健康度": ["market_health"],
    "3.2 竞争对手排行": ["rival_table"],
    "4.1 空白市场识别与排序": ["ranked_opportunities"],
    "4.2 TOP买家挖掘": ["top_buyers"],
    "5.1 核心结论": ["core_findings"],
    "5.2 风险提示": ["risks"],
    "5.3 战略建议": ["recommendations"],
}

SECTION_CHARTS_AFTER = {
    "1.3 整体出口体量": [("chart_monthly_trend", "月度出口金额趋势")],
    "1.2 覆盖市场分布": [("chart_country_amount", "主要出口国家金额分布")],
    "1.1.1 核心出口产品识别": [("chart_product_amount", "主要出口产品金额贡献")],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", action="store_true", help="Render the bundled sample metrics and analysis")
    parser.add_argument("--check-runtime", action="store_true", help="Check whether the stdlib DOCX renderer can run")
    parser.add_argument("--metrics-json", type=Path, help="Report metrics JSON file")
    parser.add_argument("--analysis-md", type=Path, help="Agent analysis Markdown with ### section headings")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE, help="Word template config JSON path")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"), help="Directory for .docx output")
    parser.add_argument("--output-name", default=None, help="Base output name without extension")
    parser.add_argument("--timestamp", action=argparse.BooleanOptionalAction, default=True, help="Append timestamp to output name")
    parser.add_argument("--self-test", action="store_true", help="Run a minimal rendering test")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check_runtime:
        return check_runtime()
    if args.self_test:
        return run_self_test(args)

    metrics_json = args.metrics_json
    analysis_md_path = args.analysis_md
    if args.sample:
        metrics_json = SAMPLE_DIR / "sample_metrics.json"
        analysis_md_path = SAMPLE_DIR / "sample_analysis.md"

    if not metrics_json or not analysis_md_path:
        print("--metrics-json and --analysis-md are required unless --sample or --self-test is used", file=sys.stderr)
        return 2

    metrics = json.loads(metrics_json.read_text(encoding="utf-8"))
    analysis_md = analysis_md_path.read_text(encoding="utf-8")
    template = load_template(args.template)
    sections = parse_agent_sections(analysis_md)
    docx_path = render_docx(
        metrics=metrics,
        sections=sections,
        template=template,
        output_dir=args.output_dir,
        output_name=args.output_name,
        timestamp=args.timestamp,
        base_dir=metrics_json.parent,
    )
    print(f"[render] DOCX: {docx_path}")
    return 0


def load_template(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def render_docx(
    metrics: dict[str, Any],
    sections: dict[str, str],
    template: dict[str, Any],
    output_dir: Path,
    output_name: str | None,
    timestamp: bool,
    base_dir: Path | None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    ensure_default_charts(metrics, output_dir, base_dir)
    company = str(metrics.get("company") or "企业")
    safe_company = safe_name(company)
    title = str(metrics.get("report_title") or template.get("title") or "企业出海贸易分析报告")
    author = str(metrics.get("author") or template.get("author") or "数据空间研究院")
    period = str(metrics.get("overall_stats", {}).get("years") or metrics.get("period") or "N/A")

    builder = DocxBuilder()
    builder.add_title(title, company, author, period)
    builder.add_toc(sections)

    used_tables: set[str] = set()
    for section_key in SECTION_ORDER:
        text = find_section(sections, section_key)
        if not text and not has_descendant_section(sections, section_key):
            continue
        level = heading_level(section_key)
        builder.add_heading(section_key, level)
        for paragraph in split_paragraphs(text):
            builder.add_markdown_paragraph(paragraph)
        for chart_field, caption in SECTION_CHARTS_AFTER.get(section_key, []):
            image_path = resolve_image(metrics.get(chart_field), base_dir)
            if image_path:
                builder.add_image(image_path, caption)
        for table_key in SECTION_TABLES_AFTER.get(section_key, []):
            if table_key not in used_tables:
                add_metric_table(builder, metrics, table_key)
                used_tables.add(table_key)

    base_name = output_name or f"{safe_company}_出海贸易分析报告"
    if timestamp:
        base_name = f"{base_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    docx_path = output_dir / f"{base_name}.docx"
    builder.save(docx_path)
    return docx_path


def parse_agent_sections(output: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []
    for line in output.splitlines():
        match = re.match(r"^###\s+(.+)$", line.strip())
        if match:
            if current_key and current_lines:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = match.group(1).strip()
            current_lines = []
        elif current_key:
            current_lines.append(line)
    if current_key and current_lines:
        sections[current_key] = "\n".join(current_lines).strip()
    return {key: value for key, value in sections.items() if value}


def find_section(sections: dict[str, str], section_key: str) -> str:
    if section_key in sections:
        return sections[section_key]
    if section_key in STRUCTURAL_ONLY_SECTIONS:
        return ""
    for alias in SECTION_ALIASES.get(section_key, []):
        if alias in sections:
            return sections[alias]
    for key, value in sections.items():
        if section_key in key or key in section_key:
            return value
    return ""


def has_descendant_section(sections: dict[str, str], section_key: str) -> bool:
    prefix = section_key.split(" ", 1)[0]
    descendant_prefix = f"{prefix}."
    return any(key.startswith(descendant_prefix) for key in sections)


def heading_level(section_key: str) -> int:
    prefix = section_key.split(" ", 1)[0]
    dots = prefix.count(".")
    return min(dots + 1, 3)


def split_paragraphs(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if paragraphs:
        return paragraphs
    return [line.strip() for line in text.splitlines() if line.strip()]


def add_metric_table(builder: "DocxBuilder", metrics: dict[str, Any], table_key: str) -> None:
    value = metrics.get(table_key)
    if not value:
        return
    builder.add_heading(TABLE_TITLES.get(table_key, table_key), 4)
    rows = rows_for_table(table_key, value)
    if rows:
        builder.add_table(rows)


def rows_for_table(table_key: str, value: Any) -> list[list[str]]:
    if table_key == "core_findings" and isinstance(value, list):
        return [["序号", "核心发现"]] + [[str(i + 1), str(item)] for i, item in enumerate(value)]
    if table_key == "risks" and isinstance(value, list):
        return [["风险类型", "说明"]] + [[str(item.get("type", "")), str(item.get("detail", ""))] for item in value if isinstance(item, dict)]
    if table_key == "recommendations" and isinstance(value, list):
        return [["优先级", "建议动作"]] + [[str(item.get("priority", "")), str(item.get("action", ""))] for item in value if isinstance(item, dict)]
    columns = TABLE_COLUMNS.get(table_key)
    if not columns or not isinstance(value, list):
        return []
    rows = [[label for _, label in columns]]
    for item in value:
        if isinstance(item, dict):
            rows.append([format_metric_value(metric_value(item, key), key) for key, _ in columns])
    return rows


def metric_value(item: dict[str, Any], key: str) -> Any:
    value = raw_metric_value(item, key)
    if value not in (None, ""):
        return value
    if key == "avg_price":
        amount = parse_number(raw_metric_value(item, "amount"))
        quantity = parse_number(raw_metric_value(item, "txn_count"))
        if amount and quantity:
            return amount / quantity
    for alias in FIELD_ALIASES.get(key, [key]):
        value = item.get(alias)
        if value not in (None, ""):
            return value
    if key == "desc":
        hs_code = normalize_hs_code(metric_value(item, "hs"))
        return HS_CODE_DESCRIPTIONS.get(hs_code, "")
    if key in MISSING_DISPLAY_KEYS:
        return "-"
    return ""


def raw_metric_value(item: dict[str, Any], key: str) -> Any:
    for alias in FIELD_ALIASES.get(key, [key]):
        value = item.get(alias)
        if value not in (None, ""):
            return value
    return ""


def format_metric_value(value: Any, key: str) -> str:
    if value in (None, ""):
        return ""
    if key == "hs":
        return normalize_hs_code(value)
    if isinstance(value, (int, float)):
        if key in {"share", "growth", "top1_customer_share", "reorder_rate"}:
            percent = value * 100 if -1 <= value <= 1 else value
            return f"{percent:.1f}%"
        if key in {"amount", "total_amount"}:
            return f"{value:,.0f}"
        if key in {"avg_price", "price_std", "price_gap_vs_target"}:
            return f"{value:,.2f}"
        if float(value).is_integer():
            return str(int(value))
    return str(value)


def metric_number(item: dict[str, Any], key: str) -> float:
    value = metric_value(item, key)
    return parse_number(value)


def parse_number(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip().replace(",", "").replace("%", "")
    if not text:
        return 0.0
    try:
        number = float(text)
    except ValueError:
        return 0.0
    if str(value).strip().endswith("%"):
        return number / 100
    return number


def normalize_hs_code(value: Any) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d+\.0", text):
        return text[:-2]
    return text


def ensure_default_charts(metrics: dict[str, Any], output_dir: Path, base_dir: Path | None) -> None:
    charts_dir = (base_dir or output_dir) / "charts"
    chart_specs = [
        ("chart_product_amount", "product_table", "hs", "amount", "主要出口产品金额贡献", charts_dir / "product_amount.png"),
        ("chart_country_amount", "country_table", "country", "amount", "主要出口国家金额分布", charts_dir / "country_amount.png"),
        ("chart_monthly_trend", "monthly_trend", "month", "amount", "月度出口金额趋势", charts_dir / "monthly_trend.png"),
    ]
    for field, table_key, label_key, value_key, title, chart_path in chart_specs:
        if resolve_image(metrics.get(field), base_dir):
            continue
        rows = metrics.get(table_key)
        if not isinstance(rows, list) or not rows:
            continue
        labels: list[str] = []
        values: list[float] = []
        for item in rows[:10]:
            if not isinstance(item, dict):
                continue
            label = format_metric_value(metric_value(item, label_key), label_key)
            amount = metric_number(item, value_key)
            if label and amount:
                labels.append(label)
                values.append(amount)
        if not labels or not values:
            continue
        if write_bar_chart(chart_path, labels, values, title):
            metrics[field] = str(chart_path)


def write_bar_chart(path: Path, labels: list[str], values: list[float], title: str) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
    except Exception as exc:
        print(f"[warn] matplotlib unavailable, skip chart {path}: {exc}", file=sys.stderr)
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    font_path = first_existing_font()
    if font_path:
        font_manager.fontManager.addfont(str(font_path))
        font_name = font_manager.FontProperties(fname=str(font_path)).get_name()
        plt.rcParams["font.sans-serif"] = [font_name]
    plt.rcParams["axes.unicode_minus"] = False

    display_values = [v / 10000 if max(values) >= 10000 else v for v in values]
    unit = "万美元" if max(values) >= 10000 else "金额"
    width = max(6.0, min(10.0, 0.8 * len(labels) + 3.0))
    fig, ax = plt.subplots(figsize=(width, 4.2), dpi=160)
    bars = ax.bar(range(len(labels)), display_values, color="#2F80ED")
    ax.set_title(title, fontsize=13, pad=12)
    ax.set_ylabel(unit)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.grid(axis="y", linestyle="--", alpha=0.25)
    ymax = max(display_values) if display_values else 1
    for bar, value in zip(bars, display_values):
        label = f"{value:,.0f}" if math.isfinite(value) else ""
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + ymax * 0.02, label, ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, format="png", bbox_inches="tight")
    plt.close(fig)
    return path.exists() and path.stat().st_size > 0


def first_existing_font() -> Path | None:
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return path
    return None


def resolve_image(value: Any, base_dir: Path | None) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    source = Path(raw)
    candidates = [source]
    if not source.is_absolute():
        if base_dir is not None:
            candidates.append(base_dir / source)
        candidates.append(Path.cwd() / source)
    existing = next((candidate.resolve() for candidate in candidates if candidate.exists()), None)
    if not existing:
        print(f"[warn] image not found: {raw}", file=sys.stderr)
        return None
    image_type = detect_image_type(existing)
    if image_type not in {"png", "jpeg"}:
        print(f"[warn] unsupported image for docx, use PNG/JPEG: {existing}", file=sys.stderr)
        return None
    return existing


def safe_name(name: str) -> str:
    return name.replace("/", "_").replace("\\", "_").replace(" ", "")


def check_runtime() -> int:
    print(f"[runtime] skill_dir: {SKILL_DIR}")
    print(f"[runtime] python: {sys.version.split()[0]}")
    print(f"[runtime] template: {'OK' if DEFAULT_TEMPLATE.exists() else 'MISSING'} {DEFAULT_TEMPLATE}")
    print(f"[runtime] sample metrics: {'OK' if (SAMPLE_DIR / 'sample_metrics.json').exists() else 'MISSING'}")
    print(f"[runtime] sample analysis: {'OK' if (SAMPLE_DIR / 'sample_analysis.md').exists() else 'MISSING'}")
    print("[runtime] docx render: available with Python standard library")
    return 0


def run_self_test(args: argparse.Namespace) -> int:
    metrics = {
        "company": "测试企业",
        "overall_stats": {"years": "2024-2025"},
        "product_table": [{"hs": "870380", "desc": "新能源乘用车", "amount": "100万元", "share": "60.0%", "txn_count": 10}],
        "core_findings": ["样例发现一", "样例发现二"],
    }
    sections = {
        "1 企业贸易全景概览": "测试企业形成连续交易记录。**样例判断。** 该段用于验证 Word 渲染。",
        "1.1.1 核心出口产品识别": "核心产品为新能源乘用车，金额100万元，占比60.0%。",
        "5.1 核心结论": "样例结论用于检查表格生成。",
    }
    with tempfile.TemporaryDirectory() as temp_dir:
        docx_path = render_docx(
            metrics=metrics,
            sections=sections,
            template=load_template(args.template),
            output_dir=Path(temp_dir),
            output_name="self_test",
            timestamp=False,
            base_dir=None,
        )
        assert docx_path.exists() and docx_path.stat().st_size > 1000
        print(f"[self-test] OK: {docx_path}")
    return 0


class DocxBuilder:
    def __init__(self) -> None:
        self.body: list[str] = []
        self.relationships: list[tuple[str, str, str]] = []
        self.media: list[tuple[Path, str]] = []
        self.next_rid = 1

    def add_title(self, title: str, company: str, author: str, period: str) -> None:
        self.add_paragraph(title, style="Title", align="center")
        self.add_paragraph(company, style="Subtitle", align="center")
        self.add_paragraph(f"分析期间：{period}", align="center")
        self.add_paragraph(author, align="center")
        self.add_paragraph(f"生成日期：{datetime.now().strftime('%Y-%m-%d')}", align="center")
        self.add_page_break()

    def add_toc(self, sections: dict[str, str]) -> None:
        self.add_heading("目 录", 1)
        for key in SECTION_ORDER:
            if key in sections or has_descendant_section(sections, key):
                indent = "　" * max(0, heading_level(key) - 1)
                self.add_paragraph(f"{indent}{key}")
        self.add_page_break()

    def add_heading(self, text: str, level: int) -> None:
        style = f"Heading{max(1, min(level, 4))}"
        self.add_paragraph(text, style=style)

    def add_markdown_paragraph(self, text: str) -> None:
        runs = parse_markdown_runs(text)
        self.body.append(paragraph_xml(runs, style=None, align=None, indent=True))

    def add_paragraph(self, text: str, style: str | None = None, align: str | None = None) -> None:
        self.body.append(paragraph_xml([(text, False)], style=style, align=align, indent=False))

    def add_page_break(self) -> None:
        self.body.append("<w:p><w:r><w:br w:type=\"page\"/></w:r></w:p>")

    def add_table(self, rows: list[list[str]]) -> None:
        self.body.append(table_xml(rows))

    def add_image(self, image_path: Path, caption: str) -> None:
        ext = ".jpg" if detect_image_type(image_path) == "jpeg" else ".png"
        media_name = f"image{len(self.media) + 1}{ext}"
        rid = f"rId{self.next_rid}"
        self.next_rid += 1
        self.relationships.append((rid, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image", f"media/{media_name}"))
        self.media.append((image_path, media_name))
        self.body.append(image_paragraph_xml(rid))
        self.add_paragraph(f"图：{caption}", align="center")

    def save(self, path: Path) -> None:
        document_xml = document_xml_text("".join(self.body))
        rels_xml = document_rels_xml(self.relationships)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as docx:
            docx.writestr("[Content_Types].xml", content_types_xml(self.media))
            docx.writestr("_rels/.rels", root_rels_xml())
            docx.writestr("word/document.xml", document_xml)
            docx.writestr("word/_rels/document.xml.rels", rels_xml)
            docx.writestr("word/styles.xml", styles_xml())
            for source, name in self.media:
                docx.write(source, f"word/media/{name}")


def sanitize_report_text(text: str) -> str:
    replacements = {
        "$\\rightarrow$": "→",
        "\\rightarrow": "→",
        "$\\to$": "→",
        "\\to": "→",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r"\s*→\s*", " → ", text).strip()


def parse_markdown_runs(text: str) -> list[tuple[str, bool]]:
    text = sanitize_report_text(text)
    runs: list[tuple[str, bool]] = []
    pos = 0
    for match in re.finditer(r"\*\*(.+?)\*\*", text):
        if match.start() > pos:
            runs.append((text[pos:match.start()], False))
        runs.append((match.group(1), True))
        pos = match.end()
    if pos < len(text):
        runs.append((text[pos:], False))
    return runs or [(text, False)]


def detect_image_type(path: Path) -> str | None:
    header = path.read_bytes()[:16]
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if header.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    return None


def paragraph_xml(runs: list[tuple[str, bool]], style: str | None, align: str | None, indent: bool) -> str:
    props: list[str] = []
    if style:
        props.append(f'<w:pStyle w:val="{xml_attr(style)}"/>')
    if align:
        props.append(f'<w:jc w:val="{xml_attr(align)}"/>')
    if indent:
        props.append('<w:ind w:firstLine="560"/>')
    props.append('<w:spacing w:line="420" w:lineRule="auto" w:after="120"/>')
    ppr = f"<w:pPr>{''.join(props)}</w:pPr>"
    return f"<w:p>{ppr}{''.join(run_xml(text, bold) for text, bold in runs)}</w:p>"


def run_xml(text: str, bold: bool = False) -> str:
    text = sanitize_report_text(text)
    rpr = (
        '<w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="方正仿宋_GB2312" w:hAnsi="Times New Roman"/>'
        '<w:sz w:val="28"/><w:szCs w:val="28"/>'
        + ("<w:b/><w:bCs/>" if bold else "")
        + "</w:rPr>"
    )
    return f"<w:r>{rpr}<w:t xml:space=\"preserve\">{xml_text(text)}</w:t></w:r>"


def table_xml(rows: list[list[str]]) -> str:
    grid_cols = max((len(row) for row in rows), default=1)
    grid = "".join('<w:gridCol w:w="1800"/>' for _ in range(grid_cols))
    body = []
    for row_index, row in enumerate(rows):
        cells = []
        for value in row:
            shade = '<w:shd w:fill="D9EAF7"/>' if row_index == 0 else ""
            cells.append(
                "<w:tc><w:tcPr>"
                '<w:tcW w:w="1800" w:type="dxa"/>'
                f"{shade}</w:tcPr>"
                f"{paragraph_xml([(str(value), row_index == 0)], style=None, align=None, indent=False)}"
                "</w:tc>"
            )
        body.append(f"<w:tr>{''.join(cells)}</w:tr>")
    return (
        "<w:tbl><w:tblPr><w:tblW w:w=\"0\" w:type=\"auto\"/>"
        "<w:tblBorders><w:top w:val=\"single\" w:sz=\"8\"/><w:left w:val=\"single\" w:sz=\"4\"/>"
        "<w:bottom w:val=\"single\" w:sz=\"8\"/><w:right w:val=\"single\" w:sz=\"4\"/>"
        "<w:insideH w:val=\"single\" w:sz=\"4\"/><w:insideV w:val=\"single\" w:sz=\"4\"/></w:tblBorders>"
        "</w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>{''.join(body)}</w:tbl>"
    )


def image_paragraph_xml(rid: str) -> str:
    cx = 5_800_000
    cy = 2_900_000
    return f"""
<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing>
<wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" distT="0" distB="0" distL="0" distR="0">
<wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="1" name="Chart"/>
<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
<pic:nvPicPr><pic:cNvPr id="0" name="Chart"/><pic:cNvPicPr/></pic:nvPicPr>
<pic:blipFill><a:blip r:embed="{xml_attr(rid)}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>
"""


def document_xml_text(body: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">
<w:body>{body}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:body>
</w:document>'''


def styles_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="方正仿宋_GB2312" w:hAnsi="Times New Roman"/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:rPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Times New Roman" w:eastAsia="方正仿宋_GB2312" w:hAnsi="Times New Roman"/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:pPr><w:jc w:val="center"/><w:spacing w:after="360"/></w:pPr><w:rPr><w:b/><w:bCs/><w:sz w:val="44"/><w:szCs w:val="44"/><w:color w:val="1A5490"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:pPr><w:jc w:val="center"/><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:bCs/><w:sz w:val="34"/><w:szCs w:val="34"/><w:color w:val="1A5490"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:spacing w:before="360" w:after="180"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:bCs/><w:sz w:val="34"/><w:szCs w:val="34"/><w:color w:val="1A5490"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:pPr><w:spacing w:before="280" w:after="160"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:bCs/><w:sz w:val="30"/><w:szCs w:val="30"/><w:color w:val="1A5490"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:pPr><w:spacing w:before="220" w:after="120"/><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:b/><w:bCs/><w:sz w:val="28"/><w:szCs w:val="28"/><w:color w:val="1A5490"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading4"><w:name w:val="heading 4"/><w:pPr><w:spacing w:before="180" w:after="100"/></w:pPr><w:rPr><w:b/><w:bCs/><w:sz w:val="26"/><w:szCs w:val="26"/></w:rPr></w:style>
</w:styles>'''


def root_rels_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''


def document_rels_xml(rels: list[tuple[str, str, str]]) -> str:
    items = ['<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>']
    items.extend(f'<Relationship Id="{xml_attr(rid)}" Type="{xml_attr(rel_type)}" Target="{xml_attr(target)}"/>' for rid, rel_type, target in rels)
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{''.join(items)}</Relationships>'''


def content_types_xml(media: list[tuple[Path, str]]) -> str:
    defaults = {
        "rels": "application/vnd.openxmlformats-package.relationships+xml",
        "xml": "application/xml",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
    }
    default_xml = "".join(f'<Default Extension="{ext}" ContentType="{ctype}"/>' for ext, ctype in defaults.items())
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
{default_xml}
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>'''


def xml_text(value: str) -> str:
    return escape(value)


def xml_attr(value: str) -> str:
    return escape(value, {'"': "&quot;"})


if __name__ == "__main__":
    raise SystemExit(main())
