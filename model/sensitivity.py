"""민감도 분석 로직."""
from __future__ import annotations

from typing import Any

import pandas as pd

from model.costs import apply_cost_scenario
from model.financials import build_financial_model
from model.revenue import apply_revenue_scenario
from model.staffing import apply_staffing_scenario


def _summary_from_model(model_result: dict[str, Any]) -> dict[str, Any]:
    """모델 결과에서 민감도 요약 지표를 추출한다."""
    labels = [col for col in model_result["pnl"].columns if str(col).startswith("Year")]
    final_year = labels[-1]
    net_income_series = model_result["series"]["net_income"]
    return {
        "최종연도": final_year,
        "최종연도 순이익": float(net_income_series[final_year]),
        "누적 순이익": float(net_income_series.sum()),
        "ROI": float(model_result["kpis"]["ROI"]),
        "투자회수기간": model_result["kpis"]["투자회수기간"],
        "1년차 손익분기매출": float(model_result["kpis"]["손익분기매출(1년차)"]),
    }


def calculate_sensitivity(
    assumptions: dict[str, Any],
    revenue_df: pd.DataFrame,
    cost_df: pd.DataFrame,
    staffing_df: pd.DataFrame,
    include_staffing_cost: bool = True,
) -> pd.DataFrame:
    """주요 변수 변화에 따른 순이익, ROI, 손익분기점 변화를 계산한다."""
    scenarios: list[dict[str, Any]] = []

    percent_steps = [-0.20, -0.10, 0.0, 0.10, 0.20]
    growth_pp_steps = [-5.0, -2.5, 0.0, 2.5, 5.0]

    for delta in growth_pp_steps:
        adj_rev = apply_revenue_scenario(revenue_df, growth_delta_pct=delta)
        result = build_financial_model(assumptions, adj_rev, cost_df, staffing_df, include_staffing_cost)
        scenarios.append({"변수": "매출 성장률", "변화": f"{delta:+.1f}%p", **_summary_from_model(result)})

    for delta in growth_pp_steps:
        adj_cost = apply_cost_scenario(cost_df, growth_delta_pct=delta)
        result = build_financial_model(assumptions, revenue_df, adj_cost, staffing_df, include_staffing_cost)
        scenarios.append({"변수": "비용 증가율", "변화": f"{delta:+.1f}%p", **_summary_from_model(result)})

    for delta in percent_steps:
        adj_rev = apply_revenue_scenario(revenue_df, price_delta=delta)
        result = build_financial_model(assumptions, adj_rev, cost_df, staffing_df, include_staffing_cost)
        scenarios.append({"변수": "객단가/단가", "변화": f"{delta:+.0%}", **_summary_from_model(result)})

    for delta in percent_steps:
        adj_rev = apply_revenue_scenario(revenue_df, volume_delta=delta)
        result = build_financial_model(assumptions, adj_rev, cost_df, staffing_df, include_staffing_cost)
        scenarios.append({"변수": "판매량/이용자 수", "변화": f"{delta:+.0%}", **_summary_from_model(result)})

    for delta in percent_steps:
        adj_staff = apply_staffing_scenario(staffing_df, salary_delta=delta)
        result = build_financial_model(assumptions, revenue_df, cost_df, adj_staff, include_staffing_cost)
        scenarios.append({"변수": "인건비", "변화": f"{delta:+.0%}", **_summary_from_model(result)})

    return pd.DataFrame(scenarios)
