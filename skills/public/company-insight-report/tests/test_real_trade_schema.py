# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


SKILL_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    path = SKILL_DIR / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_calculate_metrics_accepts_real_trade_schema(tmp_path):
    calculate = load_module("calculate_trade_metrics", "scripts/calculate_trade_metrics.py")
    excel_path = tmp_path / "real_trade.xlsx"
    output_json = tmp_path / "metrics.json"
    target_company = "安徽江淮汽车集团股份有限公司"

    rows = [
                {
                    "交易uuid": "tx-1",
                    "HS编码": "271019",
                    "供应商": target_company,
                    "采购商": "BUYER A",
            "目的国/地区": "哈萨克斯坦",
            "数量": 2,
            "单价": 100,
                    "总价": 200,
                    "交易日期": "2024-01-15",
                    "产品描述": "润滑油",
                    "产品描述中文": "变速箱油",
                    "供应商国家": "中国",
                    "采购商国家": "哈萨克斯坦",
                },
        {
            "交易uuid": "tx-2",
            "HS编码": "870421",
            "供应商": target_company,
            "采购商": "BUYER B",
            "目的国/地区": "墨西哥",
            "数量": 1,
            "单价": 300,
            "总价": 300,
            "交易日期": "2025-02-20",
            "产品描述": "货车",
            "供应商国家": "中国",
            "采购商国家": "墨西哥",
        },
        {
            "交易uuid": "tx-3",
            "HS编码": "271019",
            "供应商": "其他供应商",
            "采购商": "BUYER A",
            "目的国/地区": "哈萨克斯坦",
            "数量": 1,
            "单价": 50,
            "总价": 50,
            "交易日期": "2025-03-01",
            "产品描述": "润滑油",
            "供应商国家": "中国",
            "采购商国家": "哈萨克斯坦",
        },
    ]
    with pd.ExcelWriter(excel_path) as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="交易信息表", index=False)
        pd.DataFrame([{"字段": "目标企业", "值": target_company}]).to_excel(
            writer, sheet_name="README", index=False
        )

    metrics = calculate.calculate_metrics(excel_path, target_company, output_json)

    assert metrics["overall_stats"]["total_amount"] == 500
    assert metrics["product_table"][0]["amount"] == 300
    assert metrics["product_table"][0]["desc"] == "货车"
    assert metrics["country_table"][0]["country"] == "墨西哥"
    assert metrics["country_table"][0]["amount"] == 300
    assert metrics["top_buyers"][0]["amount"] == 300


def test_calculate_metrics_rejects_explicit_company_mismatch(tmp_path):
    calculate = load_module("calculate_trade_metrics", "scripts/calculate_trade_metrics.py")
    excel_path = tmp_path / "real_trade.xlsx"
    output_json = tmp_path / "metrics.json"
    workbook_company = "安徽江淮汽车集团股份有限公司"

    with pd.ExcelWriter(excel_path) as writer:
        pd.DataFrame(
            [
                {
                    "交易uuid": "tx-1",
                    "HS编码": "271019",
                    "供应商": workbook_company,
                    "采购商": "BUYER A",
                    "目的国/地区": "哈萨克斯坦",
                    "数量": 2,
                    "单价": 100,
                    "总价": 200,
                    "交易日期": "2025-01-15",
                    "产品描述": "润滑油",
                }
            ]
        ).to_excel(writer, sheet_name="交易信息表", index=False)
        pd.DataFrame([{"字段": "目标企业", "值": workbook_company}]).to_excel(
            writer, sheet_name="README", index=False
        )

    with pytest.raises(ValueError) as exc:
        calculate.calculate_metrics(excel_path, "奇瑞汽车股份有限公司", output_json)

    message = str(exc.value)
    assert "奇瑞汽车股份有限公司" in message
    assert workbook_company in message


def test_render_rows_accept_real_trade_field_aliases():
    render = load_module("render_company_insight_docx", "scripts/render_company_insight_docx.py")

    country_rows = render.rows_for_table(
        "country_table",
        [{"目的国/地区": "哈萨克斯坦", "总价": 3925, "占比": 0.58, "采购商数": 3}],
    )

    assert country_rows[1] == ["哈萨克斯坦", "3,925", "58.0%", "3"]


def test_render_prefers_chinese_product_description_alias():
    render = load_module("render_company_insight_docx", "scripts/render_company_insight_docx.py")

    product_rows = render.rows_for_table(
        "product_table",
        [{"HS编码": "271019", "产品描述": "MOTOR OIL", "产品描述中文": "发动机油", "总价": 100, "占比": 1, "数量": 2}],
    )

    assert product_rows[1] == ["271019", "发动机油", "100", "100.0%", "2"]


def test_render_sanitizes_latex_arrow_tokens():
    render = load_module("render_company_insight_docx", "scripts/render_company_insight_docx.py")

    runs = render.parse_markdown_runs("客户开发 $\\rightarrow$ 零件跟进 $\\rightarrow$ 订单转化")
    text = "".join(part for part, _ in runs)

    assert "$\\rightarrow$" not in text
    assert text == "客户开发 → 零件跟进 → 订单转化"
