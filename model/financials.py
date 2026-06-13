"""손익, 현금흐름, 손익분기점 계산 로직."""
from __future__ import annotations

from typing import Any

import pandas as pd

from model.common import safe_divide, to_float, year_labels
from model.costs import add_staffing_as_cost, calculate_costs
from model.revenue import calculate_revenue
from model.staffing import calculate_staffing

INITIAL_INVESTMENT_KEYS = ["보증금", "인테리어", "설비/장비", "초기재고", "인허가/컨설팅", "기타초기비용"]


def normalize_initial_investment(investment: dict[str, Any] | None) -> dict[str, float]:
    """초기투자비 딕셔너리를 표준 키로 정리한다."""
    investment = investment or {}
    return {key: to_float(investment.get(key, 0.0)) for key in INITIAL_INVESTMENT_KEYS}


def total_initial_investment(investment: dict[str, Any] | None) -> float:
    """초기투자비 총액을 계산한다."""
    return sum(normalize_initial_investment(investment).values())


def _payback_period(cash_flow: pd.DataFrame) -> str:
    """누적현금흐름이 0 이상이 되는 투자회수기간을 계산한다."""
    if cash_flow.empty:
        return "계산불가"
    prev_cum = None
    prev_year_num = 0.0
    for _, row in cash_flow.iterrows():
        year = row["연도"]
        cum = float(row["누적현금흐름"])
        if year == "Year 0":
            prev_cum = cum
            prev_year_num = 0.0
            continue
        year_num = float(str(year).replace("Year ", ""))
        if cum >= 0:
            if prev_cum is None or prev_cum >= 0:
                return f"{year_num:.1f}년"
            # 전년도 누적현금흐름에서 해당 연도 현금흐름으로 선형 보간한다.
            flow = cum - prev_cum
            fraction = abs(prev_cum) / flow if flow else 0.0
            return f"{prev_year_num + fraction:.1f}년"
        prev_cum = cum
        prev_year_num = year_num
    return "미회수"


def build_financial_model(
    assumptions: dict[str, Any],
    revenue_df: pd.DataFrame,
    cost_df: pd.DataFrame,
    staffing_df: pd.DataFrame,
    include_staffing_cost: bool = True,
) -> dict[str, Any]:
    """입력 가정을 바탕으로 재무모델 전체 결과를 생성한다."""
    years = int(assumptions.get("analysis_years", 5))
    labels = year_labels(years)
    tax_rate = to_float(assumptions.get("tax_rate_pct", 10.0)) / 100.0
    initial_investment = normalize_initial_investment(assumptions.get("initial_investment", {}))
    initial_total = total_initial_investment(initial_investment)

    revenue_result = calculate_revenue(
        revenue_df,
        years,
        global_revenue_growth_pct=to_float(assumptions.get("revenue_growth_pct", 0.0)),
    )
    staffing_result = calculate_staffing(
        staffing_df,
        years,
        global_labor_growth_pct=to_float(assumptions.get("labor_growth_pct", 0.0)),
    )
    cost_result = calculate_costs(
        cost_df,
        years,
        revenue_totals=revenue_result["totals"],
        total_headcount=staffing_result["total_headcount"],
        global_cost_growth_pct=to_float(assumptions.get("cost_growth_pct", 0.0)),
        global_labor_growth_pct=to_float(assumptions.get("labor_growth_pct", 0.0)),
        global_rent_growth_pct=to_float(assumptions.get("rent_growth_pct", 0.0)),
        global_other_growth_pct=to_float(assumptions.get("other_growth_pct", 0.0)),
    )
    if include_staffing_cost:
        cost_result = add_staffing_as_cost(cost_result, staffing_result["total_compensation"])

    revenue = revenue_result["totals"]
    total_cost = cost_result["totals"]
    cogs = cost_result["cogs"]
    depreciation = cost_result["depreciation"]
    interest = cost_result["interest"]

    gross_profit = revenue - cogs
    ebitda = revenue - (total_cost - depreciation - interest)
    operating_income = revenue - (total_cost - interest)
    profit_before_tax = operating_income - interest
    tax = profit_before_tax.apply(lambda x: max(0.0, x * tax_rate))
    net_income = profit_before_tax - tax
    cumulative_net_income = net_income.cumsum()
    operating_cash_flow = net_income + depreciation

    pnl = pd.DataFrame(
        {
            "항목": [
                "총매출",
                "매출원가",
                "매출총이익",
                "총비용",
                "EBITDA",
                "감가상각비",
                "영업이익",
                "이자비용",
                "법인세/소득세",
                "순이익",
                "누적 순이익",
                "영업이익률",
                "순이익률",
            ]
        }
    )
    for label in labels:
        pnl[label] = [
            revenue[label],
            cogs[label],
            gross_profit[label],
            total_cost[label],
            ebitda[label],
            depreciation[label],
            operating_income[label],
            interest[label],
            tax[label],
            net_income[label],
            cumulative_net_income[label],
            safe_divide(operating_income[label], revenue[label]),
            safe_divide(net_income[label], revenue[label]),
        ]

    cash_rows = [{"연도": "Year 0", "현금흐름": -initial_total, "누적현금흐름": -initial_total}]
    running_cash = -initial_total
    for label in labels:
        flow = float(operating_cash_flow[label])
        running_cash += flow
        cash_rows.append({"연도": label, "현금흐름": flow, "누적현금흐름": running_cash})
    cash_flow = pd.DataFrame(cash_rows)

    variable_cost = cost_result["variable"] + cogs.where(cogs > 0, 0)
    # cogs가 이미 variable에 포함된 경우가 많으므로 중복을 피하기 위해 max 방식이 아니라 아래 비율 계산에서는 전체 비용 상세 기준으로 처리한다.
    variable_cost_ratio = pd.Series(
        {label: safe_divide(float(cost_result["variable"].get(label, 0.0)), float(revenue.get(label, 0.0))) for label in labels},
        name="변동비율",
    )
    fixed_cost = cost_result["fixed"]
    contribution_margin_ratio = 1 - variable_cost_ratio
    break_even_revenue = pd.Series(
        {
            label: (float(fixed_cost[label]) / float(contribution_margin_ratio[label]) if contribution_margin_ratio[label] > 0 else 0.0)
            for label in labels
        },
        name="손익분기매출",
    )
    avg_price = revenue_result["avg_price"]
    break_even_units = pd.Series(
        {label: safe_divide(float(break_even_revenue[label]), float(avg_price[label])) for label in labels},
        name="손익분기판매량",
    )
    break_even = pd.DataFrame(
        {
            "연도": labels,
            "고정비": [fixed_cost[label] for label in labels],
            "변동비율": [variable_cost_ratio[label] for label in labels],
            "공헌이익률": [contribution_margin_ratio[label] for label in labels],
            "손익분기매출": [break_even_revenue[label] for label in labels],
            "가중평균단가": [avg_price[label] for label in labels],
            "손익분기판매량": [break_even_units[label] for label in labels],
        }
    )

    total_net_income = float(net_income.sum())
    roi = safe_divide(total_net_income, initial_total) if initial_total else 0.0
    payback = _payback_period(cash_flow)

    kpis = {
        "총매출": float(revenue.sum()),
        "총비용": float(total_cost.sum()),
        "영업이익": float(operating_income.sum()),
        "순이익": total_net_income,
        "영업이익률": safe_divide(float(operating_income.sum()), float(revenue.sum())),
        "순이익률": safe_divide(total_net_income, float(revenue.sum())),
        "초기투자비": initial_total,
        "투자회수기간": payback,
        "손익분기매출(1년차)": float(break_even_revenue.iloc[0]) if len(break_even_revenue) else 0.0,
        "ROI": roi,
    }

    return {
        "assumptions": assumptions,
        "revenue": revenue_result,
        "staffing": staffing_result,
        "costs": cost_result,
        "pnl": pnl,
        "cash_flow": cash_flow,
        "break_even": break_even,
        "kpis": kpis,
        "series": {
            "revenue": revenue,
            "total_cost": total_cost,
            "gross_profit": gross_profit,
            "ebitda": ebitda,
            "operating_income": operating_income,
            "net_income": net_income,
            "operating_cash_flow": operating_cash_flow,
            "cumulative_cash_flow": cash_flow.set_index("연도")["누적현금흐름"],
            "fixed_cost": fixed_cost,
            "variable_cost": cost_result["variable"],
            "depreciation": depreciation,
            "interest": interest,
        },
    }
