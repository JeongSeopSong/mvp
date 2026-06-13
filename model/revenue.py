"""매출 모델 계산 로직."""
from __future__ import annotations

from typing import Any

import pandas as pd

from model.common import clean_dataframe, pct_to_rate, to_float, year_labels

REVENUE_COLUMNS = [
    "매출항목명",
    "계산방식",
    "단가",
    "수량/이용자수",
    "일평균고객수",
    "영업일수",
    "발생주기",
    "직접입력매출",
    "연간성장률(%)",
    "비고",
]

REVENUE_FORMULAS = [
    "단가×수량",
    "객단가×일평균고객×영업일수",
    "월구독료×이용자수",
    "직접입력",
]

OCCURRENCE_OPTIONS = ["월간", "연간"]


def default_revenue_df() -> pd.DataFrame:
    """빈 기본 매출 입력표를 반환한다."""
    return pd.DataFrame(
        [
            {
                "매출항목명": "기본 제품/서비스",
                "계산방식": "단가×수량",
                "단가": 50000,
                "수량/이용자수": 100,
                "일평균고객수": 0,
                "영업일수": 0,
                "발생주기": "월간",
                "직접입력매출": 0,
                "연간성장률(%)": 5.0,
                "비고": "필요에 맞게 수정",
            }
        ],
        columns=REVENUE_COLUMNS,
    )


def normalize_revenue_df(df: pd.DataFrame | list[dict[str, Any]] | None) -> pd.DataFrame:
    """매출 입력 데이터를 표준 컬럼으로 정리한다."""
    if df is None:
        return default_revenue_df()
    out = pd.DataFrame(df).copy()
    for col in REVENUE_COLUMNS:
        if col not in out.columns:
            out[col] = "" if col in ["매출항목명", "계산방식", "발생주기", "비고"] else 0
    out = out[REVENUE_COLUMNS]
    return clean_dataframe(out, "매출항목명")


def _period_multiplier(occurrence: str) -> int:
    """월간 입력이면 12개월로 연환산하고, 연간 입력이면 1배를 적용한다."""
    return 12 if str(occurrence or "월간") == "월간" else 1


def _base_revenue_and_units(row: pd.Series) -> tuple[float, float, float]:
    """매출항목의 1년차 기준 매출, 기준 판매량, 기준 단가를 계산한다."""
    formula = str(row.get("계산방식") or "단가×수량")
    occurrence = str(row.get("발생주기") or "월간")
    multiplier = _period_multiplier(occurrence)

    unit_price = to_float(row.get("단가"))
    quantity = to_float(row.get("수량/이용자수"))
    daily_customers = to_float(row.get("일평균고객수"))
    operating_days = to_float(row.get("영업일수"))
    direct_revenue = to_float(row.get("직접입력매출"))

    if formula == "객단가×일평균고객×영업일수":
        units = daily_customers * operating_days * multiplier
        revenue = unit_price * units
        effective_price = unit_price
    elif formula == "월구독료×이용자수":
        units = quantity * multiplier
        revenue = unit_price * quantity * multiplier
        effective_price = unit_price
    elif formula == "직접입력":
        revenue = direct_revenue * multiplier
        units = quantity * multiplier if quantity > 0 else 0.0
        effective_price = revenue / units if units else 0.0
    else:
        units = quantity * multiplier
        revenue = unit_price * quantity * multiplier
        effective_price = unit_price

    return max(revenue, 0.0), max(units, 0.0), max(effective_price, 0.0)


def calculate_revenue(
    revenue_df: pd.DataFrame | list[dict[str, Any]] | None,
    years: int,
    global_revenue_growth_pct: float = 0.0,
) -> dict[str, pd.DataFrame | pd.Series | float]:
    """연도별 매출 상세, 합계, 판매량, 가중평균 단가를 계산한다."""
    df = normalize_revenue_df(revenue_df)
    labels = year_labels(years)

    detail_rows: list[dict[str, Any]] = []
    unit_rows: list[dict[str, Any]] = []
    total_by_year = {label: 0.0 for label in labels}
    units_by_year = {label: 0.0 for label in labels}

    for _, row in df.iterrows():
        base_revenue, base_units, effective_price = _base_revenue_and_units(row)
        # 항목별 성장률이 비어 있으면 전사 매출 성장률을 사용한다.
        item_growth = pct_to_rate(row.get("연간성장률(%)"), global_revenue_growth_pct / 100.0)
        item_detail = {"매출항목명": row.get("매출항목명"), "비고": row.get("비고", "")}
        item_units = {"매출항목명": row.get("매출항목명")}

        for idx, label in enumerate(labels):
            revenue = base_revenue * ((1 + item_growth) ** idx)
            units = base_units * ((1 + item_growth) ** idx)
            item_detail[label] = revenue
            item_units[label] = units
            total_by_year[label] += revenue
            units_by_year[label] += units

        detail_rows.append(item_detail)
        unit_rows.append(item_units)

    detail_df = pd.DataFrame(detail_rows)
    units_df = pd.DataFrame(unit_rows)
    totals = pd.Series(total_by_year, name="총매출")
    total_units = pd.Series(units_by_year, name="총판매량/이용건수")
    avg_price = pd.Series(
        {label: (totals[label] / total_units[label] if total_units[label] else 0.0) for label in labels},
        name="가중평균단가",
    )

    return {
        "input": df,
        "detail": detail_df,
        "units": units_df,
        "totals": totals,
        "total_units": total_units,
        "avg_price": avg_price,
    }


def apply_revenue_scenario(
    revenue_df: pd.DataFrame,
    price_delta: float = 0.0,
    volume_delta: float = 0.0,
    growth_delta_pct: float = 0.0,
) -> pd.DataFrame:
    """민감도 분석용으로 가격, 수량, 성장률을 조정한 매출 입력표를 반환한다."""
    out = normalize_revenue_df(revenue_df).copy()
    out["단가"] = out["단가"].apply(lambda x: to_float(x) * (1 + price_delta))
    out["수량/이용자수"] = out["수량/이용자수"].apply(lambda x: to_float(x) * (1 + volume_delta))
    out["일평균고객수"] = out["일평균고객수"].apply(lambda x: to_float(x) * (1 + volume_delta))
    out["직접입력매출"] = out["직접입력매출"].apply(lambda x: to_float(x) * (1 + price_delta + volume_delta))
    out["연간성장률(%)"] = out["연간성장률(%)"].apply(lambda x: to_float(x) + growth_delta_pct)
    return out
