"""Excel 다운로드 파일 생성 로직."""
from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd

from model.financials import INITIAL_INVESTMENT_KEYS, normalize_initial_investment

MONEY_FORMAT = '#,##0;[Red]-#,##0;"-"'
PERCENT_FORMAT = '0.0%'
NUMBER_FORMAT = '#,##0.0'


def _assumptions_to_df(assumptions: dict[str, Any]) -> pd.DataFrame:
    """사용자 입력 가정을 Excel용 표로 변환한다."""
    initial = normalize_initial_investment(assumptions.get("initial_investment", {}))
    rows = [
        {"구분": "기본", "항목": "사업명", "값": assumptions.get("business_name", "")},
        {"구분": "기본", "항목": "업종", "값": assumptions.get("industry", "")},
        {"구분": "기본", "항목": "분석기간(년)", "값": assumptions.get("analysis_years", "")},
        {"구분": "기본", "항목": "운영기간 단위", "값": assumptions.get("period_unit", "연간")},
        {"구분": "기본", "항목": "기준 통화", "값": assumptions.get("currency", "KRW")},
        {"구분": "세금", "항목": "세율(%)", "값": assumptions.get("tax_rate_pct", 0)},
        {"구분": "성장률", "항목": "매출 성장률(%)", "값": assumptions.get("revenue_growth_pct", 0)},
        {"구분": "성장률", "항목": "비용 증가율(%)", "값": assumptions.get("cost_growth_pct", 0)},
        {"구분": "성장률", "항목": "인건비 증가율(%)", "값": assumptions.get("labor_growth_pct", 0)},
        {"구분": "성장률", "항목": "임대료 증가율(%)", "값": assumptions.get("rent_growth_pct", 0)},
        {"구분": "성장률", "항목": "기타 비용 증가율(%)", "값": assumptions.get("other_growth_pct", 0)},
    ]
    for key in INITIAL_INVESTMENT_KEYS:
        rows.append({"구분": "초기투자비", "항목": key, "값": initial.get(key, 0)})
    rows.append({"구분": "초기투자비", "항목": "초기투자비 합계", "값": sum(initial.values())})
    return pd.DataFrame(rows)


def _format_basic_sheet(workbook, worksheet, df: pd.DataFrame, money_cols: list[str] | None = None, percent_cols: list[str] | None = None) -> None:
    """공통 Excel 서식을 적용한다."""
    header_fmt = workbook.add_format({"bold": True, "font_color": "white", "bg_color": "#1F4E78", "border": 1, "align": "center"})
    money_fmt = workbook.add_format({"num_format": MONEY_FORMAT, "border": 1})
    percent_fmt = workbook.add_format({"num_format": PERCENT_FORMAT, "border": 1})
    text_fmt = workbook.add_format({"border": 1})
    number_fmt = workbook.add_format({"num_format": NUMBER_FORMAT, "border": 1})

    for col_num, value in enumerate(df.columns.values):
        worksheet.write(0, col_num, value, header_fmt)
        width = max(12, min(28, max(len(str(value)) + 2, 14)))
        worksheet.set_column(col_num, col_num, width, text_fmt)

    money_cols = money_cols or []
    percent_cols = percent_cols or []
    for col_num, col_name in enumerate(df.columns):
        if str(col_name).startswith("Year") or col_name in money_cols or "금액" in str(col_name) or "매출" in str(col_name) or "비용" in str(col_name) or "이익" in str(col_name) or "현금흐름" in str(col_name):
            worksheet.set_column(col_num, col_num, 16, money_fmt)
        elif col_name in percent_cols or "률" in str(col_name) or "비율" in str(col_name) or col_name == "ROI":
            worksheet.set_column(col_num, col_num, 14, percent_fmt)
        elif pd.api.types.is_numeric_dtype(df[col_name]):
            worksheet.set_column(col_num, col_num, 14, number_fmt)
        else:
            worksheet.set_column(col_num, col_num, 18, text_fmt)

    worksheet.freeze_panes(1, 0)
    worksheet.autofilter(0, 0, max(len(df), 1), max(len(df.columns) - 1, 0))


def _write_dataframe(writer: pd.ExcelWriter, sheet_name: str, df: pd.DataFrame, money_cols: list[str] | None = None, percent_cols: list[str] | None = None) -> None:
    """DataFrame을 쓰고 기본 서식을 적용한다."""
    workbook = writer.book
    safe_df = df.copy()
    safe_df.to_excel(writer, sheet_name=sheet_name, index=False)
    worksheet = writer.sheets[sheet_name]
    _format_basic_sheet(workbook, worksheet, safe_df, money_cols=money_cols, percent_cols=percent_cols)


def _format_profit_and_loss(writer: pd.ExcelWriter, pnl: pd.DataFrame) -> None:
    """손익계산서 특화 서식."""
    workbook = writer.book
    worksheet = writer.sheets["Profit_and_Loss"]
    money_fmt = workbook.add_format({"num_format": MONEY_FORMAT, "border": 1})
    percent_fmt = workbook.add_format({"num_format": PERCENT_FORMAT, "border": 1})
    bold_fmt = workbook.add_format({"bold": True, "num_format": MONEY_FORMAT, "border": 1, "bg_color": "#D9EAF7"})
    bold_pct_fmt = workbook.add_format({"bold": True, "num_format": PERCENT_FORMAT, "border": 1, "bg_color": "#D9EAF7"})

    year_cols = [idx for idx, col in enumerate(pnl.columns) if str(col).startswith("Year")]
    for row_idx, item in enumerate(pnl["항목"], start=1):
        is_percent = "률" in str(item)
        is_key = item in ["총매출", "매출총이익", "EBITDA", "영업이익", "순이익", "누적 순이익", "영업이익률", "순이익률"]
        fmt = bold_pct_fmt if is_key and is_percent else bold_fmt if is_key else percent_fmt if is_percent else money_fmt
        for col_idx in year_cols:
            worksheet.write(row_idx, col_idx, pnl.iloc[row_idx - 1, col_idx], fmt)


def _add_charts_sheet(writer: pd.ExcelWriter, model_result: dict[str, Any]) -> None:
    """Charts 시트에 그래프 데이터와 Excel 기본 차트를 추가한다."""
    workbook = writer.book
    series = model_result["series"]
    revenue = series["revenue"]
    total_cost = series["total_cost"]
    operating_income = series["operating_income"]
    net_income = series["net_income"]
    cash_flow = model_result["cash_flow"]
    break_even = model_result["break_even"].set_index("연도")["손익분기매출"]

    chart_df = pd.DataFrame(
        {
            "연도": list(revenue.index),
            "총매출": list(revenue.values),
            "총비용": list(total_cost.values),
            "영업이익": list(operating_income.values),
            "순이익": list(net_income.values),
            "손익분기매출": [break_even.get(label, 0) for label in revenue.index],
        }
    )
    cumulative_df = cash_flow[["연도", "누적현금흐름"]].copy()

    chart_df.to_excel(writer, sheet_name="Charts", index=False, startrow=0)
    worksheet = writer.sheets["Charts"]
    _format_basic_sheet(workbook, worksheet, chart_df)

    startrow2 = len(chart_df) + 4
    cumulative_df.to_excel(writer, sheet_name="Charts", index=False, startrow=startrow2)
    header_fmt = workbook.add_format({"bold": True, "font_color": "white", "bg_color": "#1F4E78", "border": 1, "align": "center"})
    for col_idx, col_name in enumerate(cumulative_df.columns):
        worksheet.write(startrow2, col_idx, col_name, header_fmt)

    n = len(chart_df)
    if n == 0:
        return

    # 매출/비용 추이
    chart1 = workbook.add_chart({"type": "line"})
    for col_idx in [1, 2]:
        chart1.add_series({
            "name": ["Charts", 0, col_idx],
            "categories": ["Charts", 1, 0, n, 0],
            "values": ["Charts", 1, col_idx, n, col_idx],
        })
    chart1.set_title({"name": "매출 vs 비용"})
    chart1.set_x_axis({"name": "연도"})
    chart1.set_y_axis({"name": "금액"})
    chart1.set_size({"width": 640, "height": 360})
    worksheet.insert_chart("H2", chart1)

    # 영업이익/순이익
    chart2 = workbook.add_chart({"type": "column"})
    for col_idx in [3, 4]:
        chart2.add_series({
            "name": ["Charts", 0, col_idx],
            "categories": ["Charts", 1, 0, n, 0],
            "values": ["Charts", 1, col_idx, n, col_idx],
        })
    chart2.set_title({"name": "영업이익/순이익"})
    chart2.set_x_axis({"name": "연도"})
    chart2.set_y_axis({"name": "금액"})
    chart2.set_size({"width": 640, "height": 360})
    worksheet.insert_chart("H21", chart2)

    # 누적 현금흐름
    cumulative_n = len(cumulative_df)
    chart3 = workbook.add_chart({"type": "line"})
    chart3.add_series({
        "name": ["Charts", startrow2, 1],
        "categories": ["Charts", startrow2 + 1, 0, startrow2 + cumulative_n, 0],
        "values": ["Charts", startrow2 + 1, 1, startrow2 + cumulative_n, 1],
    })
    chart3.set_title({"name": "누적 현금흐름"})
    chart3.set_x_axis({"name": "연도"})
    chart3.set_y_axis({"name": "누적현금흐름"})
    chart3.set_size({"width": 640, "height": 360})
    worksheet.insert_chart("H40", chart3)


def build_excel_bytes(model_result: dict[str, Any], sensitivity_df: pd.DataFrame) -> bytes:
    """모델 결과 전체를 Excel 바이너리로 생성한다."""
    output = BytesIO()
    assumptions = model_result["assumptions"]
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        _write_dataframe(writer, "Input_Assumptions", _assumptions_to_df(assumptions))
        _write_dataframe(writer, "Revenue_Model", model_result["revenue"]["detail"])
        _write_dataframe(writer, "Cost_Model", model_result["costs"]["detail"])
        _write_dataframe(writer, "Staffing_Model", model_result["staffing"]["detail"])
        _write_dataframe(writer, "Profit_and_Loss", model_result["pnl"])
        _format_profit_and_loss(writer, model_result["pnl"])
        _write_dataframe(writer, "Cash_Flow", model_result["cash_flow"])
        _write_dataframe(writer, "Break_Even", model_result["break_even"], percent_cols=["변동비율", "공헌이익률"])
        _write_dataframe(writer, "Sensitivity", sensitivity_df)
        _add_charts_sheet(writer, model_result)

        # 핵심 KPI는 첫 시트 상단 오른쪽에 별도 표시한다.
        workbook = writer.book
        ws = writer.sheets["Input_Assumptions"]
        title_fmt = workbook.add_format({"bold": True, "font_color": "white", "bg_color": "#7030A0", "border": 1, "align": "center"})
        money_fmt = workbook.add_format({"num_format": MONEY_FORMAT, "border": 1})
        pct_fmt = workbook.add_format({"num_format": PERCENT_FORMAT, "border": 1})
        text_fmt = workbook.add_format({"border": 1})
        ws.write("E1", "KPI", title_fmt)
        ws.write("F1", "값", title_fmt)
        for idx, (key, value) in enumerate(model_result["kpis"].items(), start=2):
            ws.write(idx - 1, 4, key, text_fmt)
            if key in ["영업이익률", "순이익률", "ROI"]:
                ws.write(idx - 1, 5, value, pct_fmt)
            elif isinstance(value, (int, float)):
                ws.write(idx - 1, 5, value, money_fmt)
            else:
                ws.write(idx - 1, 5, value, text_fmt)
        ws.set_column("E:E", 20)
        ws.set_column("F:F", 18)

    return output.getvalue()
