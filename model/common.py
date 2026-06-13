"""공통 유틸리티 함수."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def to_float(value: Any, default: float = 0.0) -> float:
    """입력값을 float으로 변환한다. 공백/NaN/문자 오류는 기본값으로 처리한다."""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    if isinstance(value, str):
        value = value.strip().replace(",", "")
        if value == "":
            return default
        if value.endswith("%"):
            value = value[:-1]
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def pct_to_rate(value: Any, default: float = 0.0) -> float:
    """퍼센트 숫자(예: 5)를 소수율(0.05)로 변환한다."""
    return to_float(value, default * 100.0) / 100.0


def clean_dataframe(df: pd.DataFrame | None, required_name_col: str) -> pd.DataFrame:
    """동적 입력표에서 완전히 비어 있는 행과 이름 없는 행을 제거한다."""
    if df is None or len(df) == 0:
        return pd.DataFrame()
    out = df.copy()
    if required_name_col not in out.columns:
        return pd.DataFrame()
    out[required_name_col] = out[required_name_col].fillna("").astype(str).str.strip()
    out = out[out[required_name_col] != ""].copy()
    out = out.replace({np.nan: None})
    return out.reset_index(drop=True)


def year_labels(years: int) -> list[str]:
    """분석기간에 맞는 연도 라벨을 만든다."""
    return [f"Year {i}" for i in range(1, int(years) + 1)]


def safe_divide(numerator: float, denominator: float) -> float:
    """0 나눗셈을 방지하는 나눗셈."""
    if denominator == 0:
        return 0.0
    return numerator / denominator


def contains_any(text: Any, keywords: list[str]) -> bool:
    """텍스트에 특정 키워드가 포함되는지 확인한다."""
    text = str(text or "")
    return any(keyword in text for keyword in keywords)
