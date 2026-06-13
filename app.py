"""직관적인 사업 수익성 분석 Streamlit MVP."""
from __future__ import annotations

import copy
import json
from typing import Any

import pandas as pd
import streamlit as st

from model.costs import COST_TYPES, default_cost_df, normalize_cost_df
from model.financials import INITIAL_INVESTMENT_KEYS, build_financial_model
from model.revenue import OCCURRENCE_OPTIONS, REVENUE_FORMULAS, default_revenue_df, normalize_revenue_df
from model.staffing import default_staffing_df, normalize_staffing_df
from utils.charts import (
    bar_chart,
    break_even_chart,
    cost_composition_chart,
    cumulative_cash_flow_chart,
    line_chart,
)

DEFAULT_ASSUMPTIONS = {
    "business_name": "신규 사업",
    "industry": "서비스업",
    "analysis_years": 5,
    "period_unit": "연간",
    "currency": "KRW",
    "tax_rate_pct": 10.0,
    "revenue_growth_pct": 5.0,
    "cost_growth_pct": 3.0,
    "labor_growth_pct": 3.0,
    "rent_growth_pct": 2.0,
    "other_growth_pct": 3.0,
    "initial_investment": {
        "보증금": 10000000,
        "인테리어": 20000000,
        "설비/장비": 10000000,
        "초기재고": 5000000,
        "인허가/컨설팅": 3000000,
        "기타초기비용": 2000000,
    },
}

INDUSTRY_PRESETS: dict[str, dict[str, Any]] = {
    "외식업": {
        "assumptions": {
            "business_name": "외식업 신규 매장",
            "industry": "외식업",
            "analysis_years": 5,
            "currency": "KRW",
            "tax_rate_pct": 10.0,
            "revenue_growth_pct": 5.0,
            "cost_growth_pct": 3.0,
            "labor_growth_pct": 3.0,
            "rent_growth_pct": 2.0,
            "other_growth_pct": 3.0,
            "initial_investment": {
                "보증금": 10000000,
                "인테리어": 30000000,
                "설비/장비": 15000000,
                "초기재고": 3000000,
                "인허가/컨설팅": 2000000,
                "기타초기비용": 3000000,
            },
        },
        "revenue_items": [
            {
                "매출항목명": "매장 식음료 매출",
                "계산방식": "객단가×일평균고객×영업일수",
                "단가": 18000,
                "수량/이용자수": 0,
                "일평균고객수": 80,
                "영업일수": 26,
                "발생주기": "월간",
                "직접입력매출": 0,
                "연간성장률(%)": 5.0,
                "비고": "객단가와 일평균 고객 수를 조정",
            }
        ],
        "cost_items": [
            {"비용항목명": "식재료비", "비용유형": "매출연동비", "월비용": 0, "연비용": 0, "매출대비비율(%)": 32, "1인당월비용": 0, "연간증가율(%)": 0, "비고": "매출 대비 원가율"},
            {"비용항목명": "임대료", "비용유형": "고정비", "월비용": 3500000, "연비용": 0, "매출대비비율(%)": 0, "1인당월비용": 0, "연간증가율(%)": 2, "비고": ""},
            {"비용항목명": "관리비", "비용유형": "고정비", "월비용": 800000, "연비용": 0, "매출대비비율(%)": 0, "1인당월비용": 0, "연간증가율(%)": 2, "비고": ""},
            {"비용항목명": "마케팅비", "비용유형": "고정비", "월비용": 1000000, "연비용": 0, "매출대비비율(%)": 0, "1인당월비용": 0, "연간증가율(%)": 3, "비고": ""},
            {"비용항목명": "감가상각비", "비용유형": "고정비", "월비용": 0, "연비용": 8000000, "매출대비비율(%)": 0, "1인당월비용": 0, "연간증가율(%)": 0, "비고": ""},
        ],
        "staffing_items": [
            {"직무명": "점장", "인원수": 1, "1인당월급": 3300000, "4대보험/복리후생비율(%)": 12, "연봉상승률(%)": 3, "연간인원증가율(%)": 0, "비고": ""},
            {"직무명": "주방/홀 직원", "인원수": 3, "1인당월급": 2600000, "4대보험/복리후생비율(%)": 12, "연봉상승률(%)": 3, "연간인원증가율(%)": 0, "비고": ""},
        ],
    },
    "물품판매업": {
        "assumptions": {
            "business_name": "물품판매 신규 사업",
            "industry": "물품판매업",
            "analysis_years": 5,
            "currency": "KRW",
            "tax_rate_pct": 10.0,
            "revenue_growth_pct": 7.0,
            "cost_growth_pct": 3.0,
            "labor_growth_pct": 3.0,
            "rent_growth_pct": 2.0,
            "other_growth_pct": 3.0,
            "initial_investment": {
                "보증금": 8000000,
                "인테리어": 12000000,
                "설비/장비": 6000000,
                "초기재고": 25000000,
                "인허가/컨설팅": 1000000,
                "기타초기비용": 3000000,
            },
        },
        "revenue_items": [
            {"매출항목명": "주력 상품 판매", "계산방식": "단가×수량", "단가": 45000, "수량/이용자수": 900, "일평균고객수": 0, "영업일수": 0, "발생주기": "월간", "직접입력매출": 0, "연간성장률(%)": 7.0, "비고": "월 판매 수량 기준"},
            {"매출항목명": "부가 상품 판매", "계산방식": "단가×수량", "단가": 18000, "수량/이용자수": 500, "일평균고객수": 0, "영업일수": 0, "발생주기": "월간", "직접입력매출": 0, "연간성장률(%)": 5.0, "비고": ""},
        ],
        "cost_items": [
            {"비용항목명": "상품매입원가", "비용유형": "매출연동비", "월비용": 0, "연비용": 0, "매출대비비율(%)": 55, "1인당월비용": 0, "연간증가율(%)": 0, "비고": "매출 대비 매입원가"},
            {"비용항목명": "임대료/창고비", "비용유형": "고정비", "월비용": 2200000, "연비용": 0, "매출대비비율(%)": 0, "1인당월비용": 0, "연간증가율(%)": 2, "비고": ""},
            {"비용항목명": "배송/포장비", "비용유형": "매출연동비", "월비용": 0, "연비용": 0, "매출대비비율(%)": 7, "1인당월비용": 0, "연간증가율(%)": 0, "비고": ""},
            {"비용항목명": "광고비", "비용유형": "고정비", "월비용": 2500000, "연비용": 0, "매출대비비율(%)": 0, "1인당월비용": 0, "연간증가율(%)": 3, "비고": ""},
            {"비용항목명": "감가상각비", "비용유형": "고정비", "월비용": 0, "연비용": 3000000, "매출대비비율(%)": 0, "1인당월비용": 0, "연간증가율(%)": 0, "비고": ""},
        ],
        "staffing_items": [
            {"직무명": "운영/CS", "인원수": 2, "1인당월급": 2800000, "4대보험/복리후생비율(%)": 12, "연봉상승률(%)": 3, "연간인원증가율(%)": 0, "비고": ""},
            {"직무명": "물류 보조", "인원수": 1, "1인당월급": 2400000, "4대보험/복리후생비율(%)": 12, "연봉상승률(%)": 3, "연간인원증가율(%)": 0, "비고": ""},
        ],
    },
    "서비스업": {
        "assumptions": {
            "business_name": "서비스 신규 사업",
            "industry": "서비스업",
            "analysis_years": 5,
            "currency": "KRW",
            "tax_rate_pct": 10.0,
            "revenue_growth_pct": 8.0,
            "cost_growth_pct": 3.0,
            "labor_growth_pct": 4.0,
            "rent_growth_pct": 2.0,
            "other_growth_pct": 3.0,
            "initial_investment": {
                "보증금": 5000000,
                "인테리어": 8000000,
                "설비/장비": 8000000,
                "초기재고": 0,
                "인허가/컨설팅": 3000000,
                "기타초기비용": 4000000,
            },
        },
        "revenue_items": [
            {"매출항목명": "월 구독/관리 서비스", "계산방식": "월구독료×이용자수", "단가": 120000, "수량/이용자수": 180, "일평균고객수": 0, "영업일수": 0, "발생주기": "월간", "직접입력매출": 0, "연간성장률(%)": 8.0, "비고": "월 이용자 수 기준"},
            {"매출항목명": "일회성 프로젝트", "계산방식": "직접입력", "단가": 0, "수량/이용자수": 12, "일평균고객수": 0, "영업일수": 0, "발생주기": "연간", "직접입력매출": 60000000, "연간성장률(%)": 5.0, "비고": "연간 총 프로젝트 매출"},
        ],
        "cost_items": [
            {"비용항목명": "외주/서비스 원가", "비용유형": "매출연동비", "월비용": 0, "연비용": 0, "매출대비비율(%)": 20, "1인당월비용": 0, "연간증가율(%)": 0, "비고": ""},
            {"비용항목명": "사무실 임대료", "비용유형": "고정비", "월비용": 1800000, "연비용": 0, "매출대비비율(%)": 0, "1인당월비용": 0, "연간증가율(%)": 2, "비고": ""},
            {"비용항목명": "소프트웨어/툴", "비용유형": "고정비", "월비용": 700000, "연비용": 0, "매출대비비율(%)": 0, "1인당월비용": 0, "연간증가율(%)": 3, "비고": ""},
            {"비용항목명": "마케팅비", "비용유형": "고정비", "월비용": 1200000, "연비용": 0, "매출대비비율(%)": 0, "1인당월비용": 0, "연간증가율(%)": 3, "비고": ""},
            {"비용항목명": "감가상각비", "비용유형": "고정비", "월비용": 0, "연비용": 2500000, "매출대비비율(%)": 0, "1인당월비용": 0, "연간증가율(%)": 0, "비고": ""},
        ],
        "staffing_items": [
            {"직무명": "컨설턴트/담당자", "인원수": 2, "1인당월급": 3500000, "4대보험/복리후생비율(%)": 12, "연봉상승률(%)": 4, "연간인원증가율(%)": 10, "비고": ""},
            {"직무명": "운영 지원", "인원수": 1, "1인당월급": 2600000, "4대보험/복리후생비율(%)": 12, "연봉상승률(%)": 3, "연간인원증가율(%)": 0, "비고": ""},
        ],
    },
}


def format_money(value: float, currency: str = "KRW") -> str:
    """금액을 읽기 쉬운 문자열로 변환한다."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0
    if currency == "KRW":
        return f"{value:,.0f}원"
    return f"{value:,.0f} {currency}"


def format_pct(value: float) -> str:
    """비율을 퍼센트 문자열로 변환한다."""
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "0.0%"


def preset_project_data(industry: str) -> dict[str, Any]:
    """업종별 기본 입력값을 반환한다."""
    return copy.deepcopy(INDUSTRY_PRESETS.get(industry, INDUSTRY_PRESETS["서비스업"]))


def initialize_session() -> None:
    """최초 실행 시 기본 입력값을 세션에 저장한다."""
    if "data_version" not in st.session_state:
        st.session_state["data_version"] = 0
    if "assumptions" not in st.session_state:
        apply_project_data(preset_project_data("서비스업"))
        st.session_state["selected_industry"] = "서비스업"
        return
    if "revenue_df" not in st.session_state:
        st.session_state["revenue_df"] = default_revenue_df()
    if "cost_df" not in st.session_state:
        st.session_state["cost_df"] = default_cost_df()
    if "staffing_df" not in st.session_state:
        st.session_state["staffing_df"] = default_staffing_df()


def apply_project_data(data: dict[str, Any]) -> None:
    """JSON/샘플 데이터를 현재 세션에 적용한다."""
    assumptions = copy.deepcopy(DEFAULT_ASSUMPTIONS)
    assumptions.update(data.get("assumptions", {}))
    if "initial_investment" not in assumptions or assumptions["initial_investment"] is None:
        assumptions["initial_investment"] = copy.deepcopy(DEFAULT_ASSUMPTIONS["initial_investment"])
    else:
        initial = copy.deepcopy(DEFAULT_ASSUMPTIONS["initial_investment"])
        initial.update(assumptions["initial_investment"])
        assumptions["initial_investment"] = initial
    st.session_state["assumptions"] = assumptions
    st.session_state["revenue_df"] = normalize_revenue_df(data.get("revenue_items"))
    st.session_state["cost_df"] = normalize_cost_df(data.get("cost_items"))
    st.session_state["staffing_df"] = normalize_staffing_df(data.get("staffing_items"))
    st.session_state["data_version"] += 1


def export_project_json(assumptions: dict[str, Any], revenue_df: pd.DataFrame, cost_df: pd.DataFrame, staffing_df: pd.DataFrame) -> str:
    """현재 입력값을 JSON 문자열로 변환한다."""
    data = {
        "assumptions": assumptions,
        "revenue_items": revenue_df.to_dict(orient="records"),
        "cost_items": cost_df.to_dict(orient="records"),
        "staffing_items": staffing_df.to_dict(orient="records"),
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def as_float(value: Any, default: float = 0.0) -> float:
    """Streamlit 입력 위젯에 넣을 숫자를 안전하게 만든다."""
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def bump_data_version() -> None:
    """행 추가/삭제 후 위젯 키를 새로 만든다."""
    st.session_state["data_version"] += 1


def add_row(state_key: str, row: dict[str, Any], normalizer) -> None:
    """입력표에 새 행을 추가한다."""
    df = normalizer(st.session_state.get(state_key))
    st.session_state[state_key] = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    bump_data_version()
    st.rerun()


def delete_row(state_key: str, index: int, normalizer) -> None:
    """입력표에서 한 행을 삭제한다."""
    df = normalizer(st.session_state.get(state_key))
    st.session_state[state_key] = df.drop(df.index[index]).reset_index(drop=True)
    bump_data_version()
    st.rerun()


def render_revenue_inputs() -> pd.DataFrame:
    """매출 입력을 안정적인 행별 입력 UI로 렌더링한다."""
    df = normalize_revenue_df(st.session_state["revenue_df"])
    rows: list[dict[str, Any]] = []
    version = st.session_state["data_version"]

    if df.empty:
        st.info("매출항목이 없습니다. 아래 버튼으로 항목을 추가하세요.")

    for idx, row in df.iterrows():
        with st.container(border=True):
            top_cols = st.columns([2.2, 1.4, 1.1, 0.7])
            name = top_cols[0].text_input("매출항목명", value=str(row.get("매출항목명", "")), key=f"rev_name_{version}_{idx}")
            formula = str(row.get("계산방식") or REVENUE_FORMULAS[0])
            formula_index = REVENUE_FORMULAS.index(formula) if formula in REVENUE_FORMULAS else 0
            formula = top_cols[1].selectbox("계산방식", REVENUE_FORMULAS, index=formula_index, key=f"rev_formula_{version}_{idx}")
            occurrence = str(row.get("발생주기") or OCCURRENCE_OPTIONS[0])
            occurrence_index = OCCURRENCE_OPTIONS.index(occurrence) if occurrence in OCCURRENCE_OPTIONS else 0
            occurrence = top_cols[2].selectbox("발생주기", OCCURRENCE_OPTIONS, index=occurrence_index, key=f"rev_occurrence_{version}_{idx}")
            if top_cols[3].button("삭제", key=f"rev_delete_{version}_{idx}", use_container_width=True):
                delete_row("revenue_df", idx, normalize_revenue_df)

            num_cols = st.columns(6)
            unit_price = num_cols[0].number_input("단가", min_value=0.0, value=as_float(row.get("단가")), step=1000.0, key=f"rev_price_{version}_{idx}")
            quantity = num_cols[1].number_input("수량/이용자수", min_value=0.0, value=as_float(row.get("수량/이용자수")), step=1.0, key=f"rev_qty_{version}_{idx}")
            daily_customers = num_cols[2].number_input("일평균고객수", min_value=0.0, value=as_float(row.get("일평균고객수")), step=1.0, key=f"rev_daily_{version}_{idx}")
            operating_days = num_cols[3].number_input("영업일수", min_value=0.0, value=as_float(row.get("영업일수")), step=1.0, key=f"rev_days_{version}_{idx}")
            direct_revenue = num_cols[4].number_input("직접입력매출", min_value=0.0, value=as_float(row.get("직접입력매출")), step=100000.0, key=f"rev_direct_{version}_{idx}")
            growth = num_cols[5].number_input("연간성장률(%)", value=as_float(row.get("연간성장률(%)")), step=0.5, key=f"rev_growth_{version}_{idx}")
            note = st.text_input("비고", value=str(row.get("비고", "")), key=f"rev_note_{version}_{idx}")

            rows.append(
                {
                    "매출항목명": name,
                    "계산방식": formula,
                    "단가": unit_price,
                    "수량/이용자수": quantity,
                    "일평균고객수": daily_customers,
                    "영업일수": operating_days,
                    "발생주기": occurrence,
                    "직접입력매출": direct_revenue,
                    "연간성장률(%)": growth,
                    "비고": note,
                }
            )

    if st.button("매출항목 추가", key=f"rev_add_{version}"):
        add_row(
            "revenue_df",
            {
                "매출항목명": "새 매출항목",
                "계산방식": "단가×수량",
                "단가": 0,
                "수량/이용자수": 0,
                "일평균고객수": 0,
                "영업일수": 0,
                "발생주기": "월간",
                "직접입력매출": 0,
                "연간성장률(%)": 0,
                "비고": "",
            },
            normalize_revenue_df,
        )

    return normalize_revenue_df(rows)


def render_cost_inputs() -> pd.DataFrame:
    """비용 입력을 안정적인 행별 입력 UI로 렌더링한다."""
    df = normalize_cost_df(st.session_state["cost_df"])
    rows: list[dict[str, Any]] = []
    version = st.session_state["data_version"]

    if df.empty:
        st.info("비용항목이 없습니다. 아래 버튼으로 항목을 추가하세요.")

    for idx, row in df.iterrows():
        with st.container(border=True):
            top_cols = st.columns([2.2, 1.4, 0.7])
            name = top_cols[0].text_input("비용항목명", value=str(row.get("비용항목명", "")), key=f"cost_name_{version}_{idx}")
            cost_type = str(row.get("비용유형") or COST_TYPES[0])
            cost_type_index = COST_TYPES.index(cost_type) if cost_type in COST_TYPES else 0
            cost_type = top_cols[1].selectbox("비용유형", COST_TYPES, index=cost_type_index, key=f"cost_type_{version}_{idx}")
            if top_cols[2].button("삭제", key=f"cost_delete_{version}_{idx}", use_container_width=True):
                delete_row("cost_df", idx, normalize_cost_df)

            num_cols = st.columns(5)
            monthly = num_cols[0].number_input("월비용", min_value=0.0, value=as_float(row.get("월비용")), step=100000.0, key=f"cost_monthly_{version}_{idx}")
            annual = num_cols[1].number_input("연비용", min_value=0.0, value=as_float(row.get("연비용")), step=100000.0, key=f"cost_annual_{version}_{idx}")
            revenue_rate = num_cols[2].number_input("매출대비비율(%)", min_value=0.0, max_value=100.0, value=as_float(row.get("매출대비비율(%)")), step=0.5, key=f"cost_rate_{version}_{idx}")
            per_person = num_cols[3].number_input("1인당월비용", min_value=0.0, value=as_float(row.get("1인당월비용")), step=10000.0, key=f"cost_person_{version}_{idx}")
            growth = num_cols[4].number_input("연간증가율(%)", value=as_float(row.get("연간증가율(%)")), step=0.5, key=f"cost_growth_{version}_{idx}")
            note = st.text_input("비고", value=str(row.get("비고", "")), key=f"cost_note_{version}_{idx}")

            rows.append(
                {
                    "비용항목명": name,
                    "비용유형": cost_type,
                    "월비용": monthly,
                    "연비용": annual,
                    "매출대비비율(%)": revenue_rate,
                    "1인당월비용": per_person,
                    "연간증가율(%)": growth,
                    "비고": note,
                }
            )

    if st.button("비용항목 추가", key=f"cost_add_{version}"):
        add_row(
            "cost_df",
            {"비용항목명": "새 비용항목", "비용유형": "고정비", "월비용": 0, "연비용": 0, "매출대비비율(%)": 0, "1인당월비용": 0, "연간증가율(%)": 0, "비고": ""},
            normalize_cost_df,
        )

    return normalize_cost_df(rows)


def render_staffing_inputs() -> pd.DataFrame:
    """인력 입력을 안정적인 행별 입력 UI로 렌더링한다."""
    df = normalize_staffing_df(st.session_state["staffing_df"])
    rows: list[dict[str, Any]] = []
    version = st.session_state["data_version"]

    if df.empty:
        st.info("인력 항목이 없습니다. 아래 버튼으로 항목을 추가하세요.")

    for idx, row in df.iterrows():
        with st.container(border=True):
            top_cols = st.columns([2.2, 0.7])
            role = top_cols[0].text_input("직무명", value=str(row.get("직무명", "")), key=f"staff_role_{version}_{idx}")
            if top_cols[1].button("삭제", key=f"staff_delete_{version}_{idx}", use_container_width=True):
                delete_row("staffing_df", idx, normalize_staffing_df)

            num_cols = st.columns(5)
            headcount = num_cols[0].number_input("인원수", min_value=0.0, value=as_float(row.get("인원수")), step=0.5, key=f"staff_headcount_{version}_{idx}")
            salary = num_cols[1].number_input("1인당월급", min_value=0.0, value=as_float(row.get("1인당월급")), step=100000.0, key=f"staff_salary_{version}_{idx}")
            benefits = num_cols[2].number_input("4대보험/복리후생비율(%)", min_value=0.0, max_value=100.0, value=as_float(row.get("4대보험/복리후생비율(%)")), step=0.5, key=f"staff_benefits_{version}_{idx}")
            salary_growth = num_cols[3].number_input("연봉상승률(%)", value=as_float(row.get("연봉상승률(%)")), step=0.5, key=f"staff_salary_growth_{version}_{idx}")
            headcount_growth = num_cols[4].number_input("연간인원증가율(%)", value=as_float(row.get("연간인원증가율(%)")), step=0.5, key=f"staff_hc_growth_{version}_{idx}")
            note = st.text_input("비고", value=str(row.get("비고", "")), key=f"staff_note_{version}_{idx}")

            rows.append(
                {
                    "직무명": role,
                    "인원수": headcount,
                    "1인당월급": salary,
                    "4대보험/복리후생비율(%)": benefits,
                    "연봉상승률(%)": salary_growth,
                    "연간인원증가율(%)": headcount_growth,
                    "비고": note,
                }
            )

    if st.button("인력항목 추가", key=f"staff_add_{version}"):
        add_row(
            "staffing_df",
            {"직무명": "새 직무", "인원수": 0, "1인당월급": 0, "4대보험/복리후생비율(%)": 12, "연봉상승률(%)": 0, "연간인원증가율(%)": 0, "비고": ""},
            normalize_staffing_df,
        )

    return normalize_staffing_df(rows)


def formatted_financial_table(df: pd.DataFrame, currency: str) -> pd.DataFrame:
    """손익표를 UI 표시용 문자열로 변환한다."""
    out = df.copy()
    year_cols = [col for col in out.columns if str(col).startswith("Year")]
    out[year_cols] = out[year_cols].astype("object")
    for idx, row in out.iterrows():
        for col in year_cols:
            value = row[col]
            if "률" in str(row.get("항목", "")):
                out.at[idx, col] = format_pct(value)
            else:
                out.at[idx, col] = format_money(value, currency)
    return out


def formatted_break_even_table(df: pd.DataFrame, currency: str) -> pd.DataFrame:
    """손익분기점 표를 UI 표시용 문자열로 변환한다."""
    out = df.copy()
    for col in ["고정비", "손익분기매출", "가중평균단가"]:
        if col in out.columns:
            out[col] = out[col].apply(lambda x: format_money(x, currency))
    for col in ["변동비율", "공헌이익률"]:
        if col in out.columns:
            out[col] = out[col].apply(format_pct)
    if "손익분기판매량" in out.columns:
        out["손익분기판매량"] = out["손익분기판매량"].apply(lambda x: f"{float(x):,.1f}")
    return out


def render_sidebar() -> tuple[dict[str, Any], bool]:
    """사이드바 입력값을 렌더링하고 assumptions를 반환한다."""
    st.sidebar.header("기본 설정")
    current_industry = st.session_state.get("selected_industry", st.session_state.get("assumptions", {}).get("industry", "서비스업"))
    industry_options = list(INDUSTRY_PRESETS.keys())
    industry_index = industry_options.index(current_industry) if current_industry in industry_options else industry_options.index("서비스업")
    selected_industry = st.sidebar.radio("업종 기본값", industry_options, index=industry_index, horizontal=False)
    if selected_industry != st.session_state.get("selected_industry"):
        st.session_state["selected_industry"] = selected_industry
        apply_project_data(preset_project_data(selected_industry))
        st.rerun()

    if st.sidebar.button("선택 업종 기본값으로 초기화", use_container_width=True):
        st.session_state["selected_industry"] = selected_industry
        apply_project_data(preset_project_data(selected_industry))
        st.rerun()

    uploaded = st.sidebar.file_uploader("저장한 JSON 불러오기", type=["json"])
    if uploaded is not None and st.sidebar.button("업로드 JSON 적용", use_container_width=True):
        try:
            data = json.loads(uploaded.read().decode("utf-8"))
            apply_project_data(data)
            st.rerun()
        except Exception as exc:
            st.sidebar.error(f"JSON을 읽지 못했습니다: {exc}")

    assumptions = st.session_state["assumptions"].copy()
    initial = assumptions.get("initial_investment", {}).copy()

    assumptions["business_name"] = st.sidebar.text_input("사업명", value=str(assumptions.get("business_name", "")))
    assumptions["industry"] = st.sidebar.text_input("업종", value=str(assumptions.get("industry", selected_industry)))
    assumptions["analysis_years"] = st.sidebar.slider("분석기간(년)", min_value=1, max_value=10, value=int(assumptions.get("analysis_years", 5)))
    assumptions["currency"] = st.sidebar.selectbox("기준 통화", ["KRW", "USD", "JPY", "EUR"], index=["KRW", "USD", "JPY", "EUR"].index(assumptions.get("currency", "KRW")) if assumptions.get("currency", "KRW") in ["KRW", "USD", "JPY", "EUR"] else 0)
    assumptions["tax_rate_pct"] = st.sidebar.number_input("단순 세율(%)", min_value=0.0, max_value=50.0, value=float(assumptions.get("tax_rate_pct", 10.0)), step=0.5)

    st.sidebar.subheader("기본 성장률")
    assumptions["revenue_growth_pct"] = st.sidebar.number_input("매출 성장률(%)", value=float(assumptions.get("revenue_growth_pct", 5.0)), step=0.5)
    assumptions["cost_growth_pct"] = st.sidebar.number_input("비용 증가율(%)", value=float(assumptions.get("cost_growth_pct", 3.0)), step=0.5)
    assumptions["labor_growth_pct"] = st.sidebar.number_input("인건비 증가율(%)", value=float(assumptions.get("labor_growth_pct", 3.0)), step=0.5)
    assumptions["rent_growth_pct"] = st.sidebar.number_input("임대료 증가율(%)", value=float(assumptions.get("rent_growth_pct", 2.0)), step=0.5)
    assumptions["other_growth_pct"] = st.sidebar.number_input("기타 비용 증가율(%)", value=float(assumptions.get("other_growth_pct", 3.0)), step=0.5)

    st.sidebar.subheader("초기 투자비")
    for key in INITIAL_INVESTMENT_KEYS:
        initial[key] = st.sidebar.number_input(key, min_value=0, value=int(float(initial.get(key, 0))), step=1000000)
    assumptions["initial_investment"] = initial
    include_staffing_cost = st.sidebar.checkbox("인력계획을 비용에 자동 반영", value=True)

    st.session_state["assumptions"] = assumptions
    return assumptions, include_staffing_cost


def main() -> None:
    st.set_page_config(page_title="사업 수익성 분석 MVP", page_icon="📊", layout="wide")
    initialize_session()

    assumptions, include_staffing_cost = render_sidebar()
    currency = assumptions.get("currency", "KRW")

    st.title("📊 사업 수익성 분석 프로그램 MVP")
    st.caption("업종을 고른 뒤 항목명과 숫자를 직접 입력하면 화면 안에서 손익계산서, 현금흐름, 손익분기점을 바로 확인합니다.")

    input_tab, dashboard_tab, json_tab = st.tabs(["① 입력", "② 결과 대시보드", "③ 저장/복원"])

    with input_tab:
        st.subheader("A. 매출 입력")
        st.caption("매출항목명은 직접 입력할 수 있습니다. 숫자 칸도 키보드로 바로 입력됩니다.")
        st.session_state["revenue_df"] = render_revenue_inputs()

        st.subheader("B. 비용 입력")
        st.caption("고정비는 월비용 또는 연비용을 입력하고, 매출연동비는 매출대비비율을 입력합니다.")
        st.session_state["cost_df"] = render_cost_inputs()

        st.subheader("C. 인력 입력")
        st.caption("인력계획을 비용에 자동 반영하면 `인건비(인력계획)` 항목이 비용 모델에 추가됩니다.")
        st.session_state["staffing_df"] = render_staffing_inputs()

    try:
        model_result = build_financial_model(
            assumptions,
            st.session_state["revenue_df"],
            st.session_state["cost_df"],
            st.session_state["staffing_df"],
            include_staffing_cost=include_staffing_cost,
        )
    except Exception as exc:
        st.error(f"모델 계산 중 오류가 발생했습니다: {exc}")
        st.stop()

    with input_tab:
        st.divider()
        st.subheader("바로 확인")
        st.caption("입력값을 바꾸면 자동으로 다시 계산됩니다. 결과는 `② 결과 대시보드`에서 확인하세요.")

    with dashboard_tab:
        kpis = model_result["kpis"]
        st.subheader("핵심 KPI")
        metric_cols = st.columns(4)
        metric_cols[0].metric("총매출", format_money(kpis["총매출"], currency))
        metric_cols[1].metric("총비용", format_money(kpis["총비용"], currency))
        metric_cols[2].metric("영업이익", format_money(kpis["영업이익"], currency))
        metric_cols[3].metric("순이익", format_money(kpis["순이익"], currency))

        metric_cols = st.columns(4)
        metric_cols[0].metric("영업이익률", format_pct(kpis["영업이익률"]))
        metric_cols[1].metric("투자회수기간", str(kpis["투자회수기간"]))
        metric_cols[2].metric("손익분기 매출(1년차)", format_money(kpis["손익분기매출(1년차)"], currency))
        metric_cols[3].metric("ROI", format_pct(kpis["ROI"]))

        if include_staffing_cost and st.session_state["cost_df"]["비용항목명"].astype(str).str.contains("인건비|급여|급료", regex=True).any():
            st.warning("비용 입력표에 인건비성 항목이 있고, 인력계획도 비용에 자동 반영 중입니다. 중복 반영 여부를 확인하세요.")

        st.divider()
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.plotly_chart(
                line_chart({"총매출": model_result["series"]["revenue"]}, "연도별 매출 추이"),
                use_container_width=True,
            )
        with chart_col2:
            st.plotly_chart(
                line_chart({"총비용": model_result["series"]["total_cost"]}, "연도별 비용 추이"),
                use_container_width=True,
            )

        chart_col3, chart_col4 = st.columns(2)
        with chart_col3:
            st.plotly_chart(
                bar_chart(
                    {
                        "영업이익": model_result["series"]["operating_income"],
                        "순이익": model_result["series"]["net_income"],
                    },
                    "연도별 영업이익/순이익",
                ),
                use_container_width=True,
            )
        with chart_col4:
            year_options = [col for col in model_result["costs"]["detail"].columns if str(col).startswith("Year")]
            if year_options:
                selected_year = st.selectbox("비용 구성 기준 연도", year_options, index=0)
                st.plotly_chart(cost_composition_chart(model_result["costs"]["detail"], selected_year), use_container_width=True)
            else:
                st.info("비용항목이 없어 비용 구성 차트를 표시하지 않습니다.")

        chart_col5, chart_col6 = st.columns(2)
        with chart_col5:
            st.plotly_chart(cumulative_cash_flow_chart(model_result["cash_flow"]), use_container_width=True)
        with chart_col6:
            st.plotly_chart(break_even_chart(model_result["break_even"], model_result["series"]["revenue"]), use_container_width=True)

        st.subheader("손익계산서")
        st.dataframe(formatted_financial_table(model_result["pnl"], currency), hide_index=True, use_container_width=True)

        st.subheader("현금흐름")
        cash_display = model_result["cash_flow"].copy()
        for col in ["현금흐름", "누적현금흐름"]:
            cash_display[col] = cash_display[col].apply(lambda x: format_money(x, currency))
        st.dataframe(cash_display, hide_index=True, use_container_width=True)

        st.subheader("손익분기점")
        st.dataframe(formatted_break_even_table(model_result["break_even"], currency), hide_index=True, use_container_width=True)

    with json_tab:
        st.subheader("현재 입력값 JSON 저장")
        project_json = export_project_json(
            assumptions,
            st.session_state["revenue_df"],
            st.session_state["cost_df"],
            st.session_state["staffing_df"],
        )
        st.download_button(
            "입력값 JSON 다운로드",
            data=project_json,
            file_name="business_profitability_inputs.json",
            mime="application/json",
            use_container_width=True,
        )
        with st.expander("JSON 미리보기"):
            st.code(project_json, language="json")


if __name__ == "__main__":
    main()
