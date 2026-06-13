"""대시보드 Plotly 차트 생성 함수."""
from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def _series_dict_to_long(series_dict: dict[str, pd.Series], value_name: str = "금액") -> pd.DataFrame:
    """여러 Series를 Plotly용 long format으로 변환한다."""
    rows: list[dict[str, Any]] = []
    for name, series in series_dict.items():
        for year, value in series.items():
            rows.append({"연도": year, "항목": name, value_name: float(value)})
    return pd.DataFrame(rows)


def line_chart(series_dict: dict[str, pd.Series], title: str, value_name: str = "금액") -> go.Figure:
    """연도별 추이 라인 차트."""
    df = _series_dict_to_long(series_dict, value_name=value_name)
    fig = px.line(df, x="연도", y=value_name, color="항목", markers=True, title=title)
    fig.update_layout(legend_title_text="항목", yaxis_title=value_name)
    return fig


def bar_chart(series_dict: dict[str, pd.Series], title: str, value_name: str = "금액") -> go.Figure:
    """연도별 비교 막대 차트."""
    df = _series_dict_to_long(series_dict, value_name=value_name)
    fig = px.bar(df, x="연도", y=value_name, color="항목", barmode="group", title=title)
    fig.update_layout(legend_title_text="항목", yaxis_title=value_name)
    return fig


def cost_composition_chart(cost_detail: pd.DataFrame, year_label: str) -> go.Figure:
    """특정 연도의 비용 구성 막대 차트."""
    if cost_detail.empty or year_label not in cost_detail.columns:
        return go.Figure()
    df = cost_detail[["비용항목명", year_label]].copy()
    df = df[df[year_label] > 0].sort_values(year_label, ascending=False)
    fig = px.bar(df, x="비용항목명", y=year_label, title=f"비용 구성 - {year_label}")
    fig.update_layout(xaxis_title="비용항목", yaxis_title="금액")
    return fig


def cumulative_cash_flow_chart(cash_flow_df: pd.DataFrame) -> go.Figure:
    """누적 현금흐름 차트."""
    fig = px.line(cash_flow_df, x="연도", y="누적현금흐름", markers=True, title="누적 현금흐름")
    fig.add_hline(y=0, line_dash="dash")
    fig.update_layout(yaxis_title="누적현금흐름")
    return fig


def break_even_chart(break_even_df: pd.DataFrame, revenue_series: pd.Series) -> go.Figure:
    """실제 매출과 손익분기 매출 비교 차트."""
    rows: list[dict[str, Any]] = []
    for year, value in revenue_series.items():
        rows.append({"연도": year, "항목": "예상 매출", "금액": float(value)})
    for _, row in break_even_df.iterrows():
        rows.append({"연도": row["연도"], "항목": "손익분기 매출", "금액": float(row["손익분기매출"])})
    df = pd.DataFrame(rows)
    fig = px.line(df, x="연도", y="금액", color="항목", markers=True, title="손익분기점 분석")
    fig.update_layout(legend_title_text="항목", yaxis_title="금액")
    return fig


def sensitivity_chart(sensitivity_df: pd.DataFrame) -> go.Figure:
    """민감도 분석 결과 차트."""
    if sensitivity_df.empty:
        return go.Figure()
    fig = px.bar(
        sensitivity_df,
        x="변화",
        y="최종연도 순이익",
        color="변수",
        barmode="group",
        title="민감도 분석 - 최종연도 순이익",
    )
    fig.update_layout(xaxis_title="변화", yaxis_title="최종연도 순이익")
    return fig
