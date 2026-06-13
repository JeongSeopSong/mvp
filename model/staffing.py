"""인력계획 및 인건비 계산 로직."""
from __future__ import annotations

from typing import Any

import pandas as pd

from model.common import clean_dataframe, pct_to_rate, to_float, year_labels

STAFFING_COLUMNS = [
    "직무명",
    "인원수",
    "1인당월급",
    "4대보험/복리후생비율(%)",
    "연봉상승률(%)",
    "연간인원증가율(%)",
    "비고",
]


def default_staffing_df() -> pd.DataFrame:
    """기본 인력 입력표를 반환한다."""
    return pd.DataFrame(
        [
            {"직무명": "대표/관리자", "인원수": 1, "1인당월급": 3000000, "4대보험/복리후생비율(%)": 12, "연봉상승률(%)": 3, "연간인원증가율(%)": 0, "비고": "필요 시 수정"},
            {"직무명": "직원", "인원수": 1, "1인당월급": 2500000, "4대보험/복리후생비율(%)": 12, "연봉상승률(%)": 3, "연간인원증가율(%)": 0, "비고": "필요 시 수정"},
        ],
        columns=STAFFING_COLUMNS,
    )


def normalize_staffing_df(df: pd.DataFrame | list[dict[str, Any]] | None) -> pd.DataFrame:
    """인력 입력 데이터를 표준 컬럼으로 정리한다."""
    if df is None:
        return default_staffing_df()
    out = pd.DataFrame(df).copy()
    for col in STAFFING_COLUMNS:
        if col not in out.columns:
            out[col] = "" if col in ["직무명", "비고"] else 0
    out = out[STAFFING_COLUMNS]
    return clean_dataframe(out, "직무명")


def calculate_staffing(
    staffing_df: pd.DataFrame | list[dict[str, Any]] | None,
    years: int,
    global_labor_growth_pct: float = 0.0,
) -> dict[str, pd.DataFrame | pd.Series]:
    """연도별 인력 수와 총 인건비를 계산한다."""
    df = normalize_staffing_df(staffing_df)
    labels = year_labels(years)
    rows: list[dict[str, Any]] = []
    headcount_rows: list[dict[str, Any]] = []
    total_comp = {label: 0.0 for label in labels}
    total_headcount = {label: 0.0 for label in labels}

    for _, row in df.iterrows():
        role = row.get("직무명")
        base_headcount = to_float(row.get("인원수"))
        monthly_salary = to_float(row.get("1인당월급"))
        benefits_rate = pct_to_rate(row.get("4대보험/복리후생비율(%)"))
        salary_growth = pct_to_rate(row.get("연봉상승률(%)"), global_labor_growth_pct / 100.0)
        headcount_growth = pct_to_rate(row.get("연간인원증가율(%)"))

        comp_row = {"직무명": role, "비고": row.get("비고", "")}
        hc_row = {"직무명": role}
        for idx, label in enumerate(labels):
            # 인원수는 소수도 허용한다. 필요하면 UI에서 정수로 입력하면 된다.
            headcount = base_headcount * ((1 + headcount_growth) ** idx)
            salary = monthly_salary * ((1 + salary_growth) ** idx)
            annual_comp = headcount * salary * 12 * (1 + benefits_rate)
            comp_row[label] = annual_comp
            hc_row[label] = headcount
            total_comp[label] += annual_comp
            total_headcount[label] += headcount
        rows.append(comp_row)
        headcount_rows.append(hc_row)

    return {
        "input": df,
        "detail": pd.DataFrame(rows),
        "headcount_detail": pd.DataFrame(headcount_rows),
        "total_compensation": pd.Series(total_comp, name="총인건비"),
        "total_headcount": pd.Series(total_headcount, name="총인원"),
    }


def apply_staffing_scenario(staffing_df: pd.DataFrame, salary_delta: float = 0.0) -> pd.DataFrame:
    """민감도 분석용으로 급여 수준을 조정한 인력 입력표를 반환한다."""
    out = normalize_staffing_df(staffing_df).copy()
    out["1인당월급"] = out["1인당월급"].apply(lambda x: to_float(x) * (1 + salary_delta))
    return out
