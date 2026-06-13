"""비용 모델 계산 로직."""
from __future__ import annotations

from typing import Any

import pandas as pd

from model.common import clean_dataframe, contains_any, pct_to_rate, to_float, year_labels

COST_COLUMNS = [
    "비용항목명",
    "비용유형",
    "월비용",
    "연비용",
    "매출대비비율(%)",
    "1인당월비용",
    "연간증가율(%)",
    "비고",
]

COST_TYPES = ["고정비", "변동비", "매출연동비", "인원연동비"]

COGS_KEYWORDS = ["매출원가", "원가", "식재료", "재료비", "상품매입", "제품매입"]
DEPRECIATION_KEYWORDS = ["감가상각"]
INTEREST_KEYWORDS = ["이자"]
RENT_KEYWORDS = ["임대료", "월세", "렌트"]
LABOR_KEYWORDS = ["인건비", "급여", "급료", "직원"]
OTHER_KEYWORDS = ["기타"]


def default_cost_df() -> pd.DataFrame:
    """기본 비용 입력표를 반환한다."""
    rows = [
        {"비용항목명": "매출원가", "비용유형": "매출연동비", "월비용": 0, "연비용": 0, "매출대비비율(%)": 35, "1인당월비용": 0, "연간증가율(%)": 0, "비고": "재료비/상품매입 등"},
        {"비용항목명": "임대료", "비용유형": "고정비", "월비용": 2000000, "연비용": 0, "매출대비비율(%)": 0, "1인당월비용": 0, "연간증가율(%)": 2, "비고": "월세"},
        {"비용항목명": "관리비", "비용유형": "고정비", "월비용": 500000, "연비용": 0, "매출대비비율(%)": 0, "1인당월비용": 0, "연간증가율(%)": 2, "비고": "공용관리비"},
        {"비용항목명": "마케팅비", "비용유형": "고정비", "월비용": 1000000, "연비용": 0, "매출대비비율(%)": 0, "1인당월비용": 0, "연간증가율(%)": 3, "비고": "광고/판촉"},
        {"비용항목명": "감가상각비", "비용유형": "고정비", "월비용": 0, "연비용": 3000000, "매출대비비율(%)": 0, "1인당월비용": 0, "연간증가율(%)": 0, "비고": "단순 정액 가정"},
    ]
    return pd.DataFrame(rows, columns=COST_COLUMNS)


def normalize_cost_df(df: pd.DataFrame | list[dict[str, Any]] | None) -> pd.DataFrame:
    """비용 입력 데이터를 표준 컬럼으로 정리한다."""
    if df is None:
        return default_cost_df()
    out = pd.DataFrame(df).copy()
    for col in COST_COLUMNS:
        if col not in out.columns:
            out[col] = "" if col in ["비용항목명", "비용유형", "비고"] else 0
    out = out[COST_COLUMNS]
    return clean_dataframe(out, "비용항목명")


def _growth_for_cost(row: pd.Series, global_rates: dict[str, float]) -> float:
    """비용 항목명 기반으로 기본 증가율을 보정한다."""
    raw = row.get("연간증가율(%)")
    if raw not in [None, ""]:
        return pct_to_rate(raw)

    name = str(row.get("비용항목명") or "")
    if contains_any(name, LABOR_KEYWORDS):
        return global_rates.get("labor", 0.0)
    if contains_any(name, RENT_KEYWORDS):
        return global_rates.get("rent", 0.0)
    if contains_any(name, OTHER_KEYWORDS):
        return global_rates.get("other", 0.0)
    return global_rates.get("cost", 0.0)


def calculate_costs(
    cost_df: pd.DataFrame | list[dict[str, Any]] | None,
    years: int,
    revenue_totals: pd.Series,
    total_headcount: pd.Series | None = None,
    global_cost_growth_pct: float = 0.0,
    global_labor_growth_pct: float = 0.0,
    global_rent_growth_pct: float = 0.0,
    global_other_growth_pct: float = 0.0,
) -> dict[str, pd.DataFrame | pd.Series]:
    """연도별 비용 상세와 주요 비용 분류 합계를 계산한다."""
    df = normalize_cost_df(cost_df)
    labels = year_labels(years)
    headcount = total_headcount if total_headcount is not None else pd.Series({label: 0.0 for label in labels})
    global_rates = {
        "cost": global_cost_growth_pct / 100.0,
        "labor": global_labor_growth_pct / 100.0,
        "rent": global_rent_growth_pct / 100.0,
        "other": global_other_growth_pct / 100.0,
    }

    rows: list[dict[str, Any]] = []
    total = {label: 0.0 for label in labels}
    variable = {label: 0.0 for label in labels}
    fixed = {label: 0.0 for label in labels}
    cogs = {label: 0.0 for label in labels}
    depreciation = {label: 0.0 for label in labels}
    interest = {label: 0.0 for label in labels}

    for _, row in df.iterrows():
        name = str(row.get("비용항목명") or "")
        cost_type = str(row.get("비용유형") or "고정비")
        monthly_cost = to_float(row.get("월비용"))
        annual_cost = to_float(row.get("연비용"))
        revenue_rate = pct_to_rate(row.get("매출대비비율(%)"))
        per_person_monthly = to_float(row.get("1인당월비용"))
        growth = _growth_for_cost(row, global_rates)
        base_fixed = annual_cost if annual_cost > 0 else monthly_cost * 12

        item = {"비용항목명": name, "비용유형": cost_type, "비고": row.get("비고", "")}
        for idx, label in enumerate(labels):
            if cost_type in ["매출연동비", "변동비"] and revenue_rate > 0:
                amount = float(revenue_totals.get(label, 0.0)) * revenue_rate
                variable[label] += amount
            elif cost_type == "인원연동비":
                amount = per_person_monthly * float(headcount.get(label, 0.0)) * 12 * ((1 + growth) ** idx)
                fixed[label] += amount
            else:
                amount = base_fixed * ((1 + growth) ** idx)
                fixed[label] += amount

            item[label] = amount
            total[label] += amount
            if contains_any(name, COGS_KEYWORDS):
                cogs[label] += amount
            if contains_any(name, DEPRECIATION_KEYWORDS):
                depreciation[label] += amount
            if contains_any(name, INTEREST_KEYWORDS):
                interest[label] += amount
        rows.append(item)

    detail_df = pd.DataFrame(rows)
    return {
        "input": df,
        "detail": detail_df,
        "totals": pd.Series(total, name="총비용"),
        "fixed": pd.Series(fixed, name="고정비"),
        "variable": pd.Series(variable, name="변동비/매출연동비"),
        "cogs": pd.Series(cogs, name="매출원가"),
        "depreciation": pd.Series(depreciation, name="감가상각비"),
        "interest": pd.Series(interest, name="이자비용"),
    }


def add_staffing_as_cost(cost_result: dict[str, pd.DataFrame | pd.Series], staffing_costs: pd.Series) -> dict[str, pd.DataFrame | pd.Series]:
    """인력계획에서 계산된 인건비를 비용 모델에 별도 비용항목으로 추가한다."""
    if staffing_costs is None or staffing_costs.empty or staffing_costs.sum() == 0:
        return cost_result

    labels = list(staffing_costs.index)
    detail = cost_result["detail"].copy()
    staffing_row = {"비용항목명": "인건비(인력계획)", "비용유형": "인원연동비", "비고": "Staffing_Model 자동 반영"}
    for label in labels:
        staffing_row[label] = float(staffing_costs.get(label, 0.0))
    detail = pd.concat([detail, pd.DataFrame([staffing_row])], ignore_index=True)

    out = cost_result.copy()
    out["detail"] = detail
    out["totals"] = cost_result["totals"] + staffing_costs
    out["fixed"] = cost_result["fixed"] + staffing_costs
    return out


def apply_cost_scenario(
    cost_df: pd.DataFrame,
    fixed_cost_delta: float = 0.0,
    revenue_rate_delta: float = 0.0,
    growth_delta_pct: float = 0.0,
) -> pd.DataFrame:
    """민감도 분석용으로 비용 금액/비율/증가율을 조정한 비용 입력표를 반환한다."""
    out = normalize_cost_df(cost_df).copy()
    out["월비용"] = out["월비용"].apply(lambda x: to_float(x) * (1 + fixed_cost_delta))
    out["연비용"] = out["연비용"].apply(lambda x: to_float(x) * (1 + fixed_cost_delta))
    out["1인당월비용"] = out["1인당월비용"].apply(lambda x: to_float(x) * (1 + fixed_cost_delta))
    out["매출대비비율(%)"] = out["매출대비비율(%)"].apply(lambda x: max(0.0, to_float(x) * (1 + revenue_rate_delta)))
    out["연간증가율(%)"] = out["연간증가율(%)"].apply(lambda x: to_float(x) + growth_delta_pct)
    return out
