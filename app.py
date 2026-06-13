"""직관적인 사업 수익성 분석 Streamlit MVP."""
from __future__ import annotations

import copy
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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

BASE_DIR = Path(__file__).resolve().parent
FONT_DIR = BASE_DIR / "assets" / "fonts"
SLIDE_W = 1920
SLIDE_H = 1080
SLIDE_MARGIN = 92
COLORS = {
    "bg": "#F7F5F2",
    "paper": "#FFFFFF",
    "ink": "#222222",
    "muted": "#6B6B6B",
    "line": "#D8D2CB",
    "dark": "#2D2D2D",
    "red": "#D04A02",
    "orange": "#EB8C00",
    "yellow": "#FFB600",
    "rose": "#DB536A",
    "green": "#2E7D32",
}

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
    """업종 기본값 데이터를 현재 세션에 적용한다."""
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


def pdf_filename(assumptions: dict[str, Any]) -> str:
    """사업명 기반의 PDF 파일명을 만든다."""
    raw_name = str(assumptions.get("business_name") or "business_report").strip()
    safe_name = "".join(ch if ch.isalnum() or ch in (" ", "_", "-") else "_" for ch in raw_name).strip()
    return f"{safe_name.replace(' ', '_') or 'business_report'}_report.pdf"


def load_slide_fonts() -> dict[str, ImageFont.FreeTypeFont]:
    """Pretendard 기반 슬라이드 폰트를 로드한다."""
    regular = FONT_DIR / "Pretendard-Regular.otf"
    semibold = FONT_DIR / "Pretendard-SemiBold.otf"
    bold = FONT_DIR / "Pretendard-Bold.otf"
    return {
        "title": ImageFont.truetype(str(bold), 60),
        "subtitle": ImageFont.truetype(str(regular), 26),
        "page_title": ImageFont.truetype(str(bold), 38),
        "section": ImageFont.truetype(str(semibold), 25),
        "kpi_label": ImageFont.truetype(str(semibold), 20),
        "kpi_value": ImageFont.truetype(str(bold), 34),
        "body": ImageFont.truetype(str(regular), 19),
        "body_sm": ImageFont.truetype(str(regular), 16),
        "body_xs": ImageFont.truetype(str(regular), 13),
        "table_head": ImageFont.truetype(str(semibold), 17),
        "table": ImageFont.truetype(str(regular), 15),
        "table_bold": ImageFont.truetype(str(semibold), 15),
        "chart": ImageFont.truetype(str(regular), 14),
        "chart_bold": ImageFont.truetype(str(semibold), 15),
        "footer": ImageFont.truetype(str(regular), 13),
    }


def hex_color(name_or_hex: str) -> str:
    """색상 이름 또는 hex 값을 반환한다."""
    return COLORS.get(name_or_hex, name_or_hex)


def make_slide(title: str, subtitle: str = "", page_no: int | None = None, fonts: dict[str, ImageFont.FreeTypeFont] | None = None) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """공통 슬라이드 배경과 헤더를 만든다."""
    fonts = fonts or load_slide_fonts()
    image = Image.new("RGB", (SLIDE_W, SLIDE_H), hex_color("bg"))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, SLIDE_W, 16], fill=hex_color("dark"))
    draw.rectangle([0, 0, 430, 16], fill=hex_color("red"))
    draw.rectangle([430, 0, 650, 16], fill=hex_color("orange"))
    draw.text((SLIDE_MARGIN, 58), title, font=fonts["page_title"], fill=hex_color("ink"))
    if subtitle:
        draw.text((SLIDE_MARGIN, 108), subtitle, font=fonts["body"], fill=hex_color("muted"))
    draw.line([SLIDE_MARGIN, SLIDE_H - 58, SLIDE_W - SLIDE_MARGIN, SLIDE_H - 58], fill=hex_color("line"), width=2)
    draw.text((SLIDE_MARGIN, SLIDE_H - 42), "Business Profitability Assessment", font=fonts["footer"], fill=hex_color("muted"))
    if page_no is not None:
        draw.text((SLIDE_W - SLIDE_MARGIN - 35, SLIDE_H - 42), str(page_no), font=fonts["footer"], fill=hex_color("muted"))
    return image, draw


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    """텍스트 크기를 반환한다."""
    bbox = draw.textbbox((0, 0), str(text), font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: Any,
    xy: tuple[int, int],
    max_width: int,
    font: ImageFont.FreeTypeFont,
    fill: str,
    line_gap: int = 6,
    max_lines: int | None = None,
) -> int:
    """한글/영문 텍스트를 박스 너비에 맞게 줄바꿈해 그린다."""
    words = str(text or "").replace("\n", " ").split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if text_size(draw, candidate, font)[0] <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        while text_size(draw, current, font)[0] > max_width and len(current) > 1:
            cut = len(current) - 1
            while cut > 1 and text_size(draw, current[:cut] + "...", font)[0] > max_width:
                cut -= 1
            lines.append(current[:cut] + "...")
            current = current[cut:]
    if current:
        lines.append(current)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while text_size(draw, last + "...", font)[0] > max_width and len(last) > 1:
            last = last[:-1]
        lines[-1] = last + "..."
    x, y = xy
    line_height = text_size(draw, "Ag", font)[1] + line_gap
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def rounded_card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str = "paper", outline: str = "line", radius: int = 14) -> None:
    """공통 카드 박스를 그린다."""
    draw.rounded_rectangle(box, radius=radius, fill=hex_color(fill), outline=hex_color(outline), width=2)


def format_million(value: Any, suffix: str = "백만원") -> str:
    """금액을 백만원 단위로 표기한다."""
    try:
        amount = float(value) / 1_000_000
    except (TypeError, ValueError):
        amount = 0.0
    return f"{amount:,.1f}{suffix}"


def format_number_1(value: Any) -> str:
    """숫자를 소수점 1자리로 표기한다."""
    try:
        return f"{float(value):,.1f}"
    except (TypeError, ValueError):
        return "0.0"


def pct_display(value: Any, already_percent: bool = False) -> str:
    """비율을 % 단위로 표기한다."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    if not already_percent:
        number *= 100
    return f"{number:,.1f}%"


def draw_kpi_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    value: str,
    note: str,
    fonts: dict[str, ImageFont.FreeTypeFont],
    accent: str = "red",
) -> None:
    """KPI 카드."""
    rounded_card(draw, box)
    x1, y1, x2, y2 = box
    draw.rectangle([x1, y1, x1 + 10, y2], fill=hex_color(accent))
    draw.text((x1 + 26, y1 + 20), label, font=fonts["kpi_label"], fill=hex_color("muted"))
    draw.text((x1 + 26, y1 + 54), value, font=fonts["kpi_value"], fill=hex_color("ink"))
    draw_wrapped_text(draw, note, (x1 + 26, y1 + 100), x2 - x1 - 48, fonts["body_xs"], hex_color("muted"), max_lines=2)


def draw_small_table(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    headers: list[str],
    rows: list[list[Any]],
    col_widths: list[float],
    fonts: dict[str, ImageFont.FreeTypeFont],
    money_cols: set[int] | None = None,
    highlight_rows: set[int] | None = None,
    max_rows: int | None = None,
) -> None:
    """슬라이드용 가독성 높은 표."""
    money_cols = money_cols or set()
    highlight_rows = highlight_rows or set()
    if max_rows is not None:
        rows = rows[:max_rows]
    x1, y1, x2, y2 = box
    rounded_card(draw, box)
    draw.text((x1 + 22, y1 + 18), title, font=fonts["section"], fill=hex_color("ink"))
    table_x = x1 + 22
    table_y = y1 + 58
    table_w = x2 - x1 - 44
    available_h = y2 - table_y - 20
    row_count = max(len(rows) + 1, 1)
    row_h = max(34, min(48, available_h // row_count))
    widths = [int(table_w * width / sum(col_widths)) for width in col_widths]
    widths[-1] += table_w - sum(widths)
    draw.rounded_rectangle([table_x, table_y, table_x + table_w, table_y + row_h], radius=8, fill=hex_color("dark"))
    cx = table_x
    for idx, header in enumerate(headers):
        draw_wrapped_text(draw, header, (cx + 8, table_y + 9), widths[idx] - 16, fonts["table_head"], "#FFFFFF", line_gap=2, max_lines=1)
        cx += widths[idx]
    for row_idx, row in enumerate(rows):
        y = table_y + row_h * (row_idx + 1)
        fill = "#F6EEE8" if row_idx in highlight_rows else ("#FFFFFF" if row_idx % 2 == 0 else "#FAFAFA")
        draw.rectangle([table_x, y, table_x + table_w, y + row_h], fill=fill)
        cx = table_x
        for col_idx, cell in enumerate(row):
            text = str(cell)
            font = fonts["table_bold"] if row_idx in highlight_rows else fonts["table"]
            if col_idx in money_cols:
                tw, _ = text_size(draw, text, font)
                draw.text((cx + widths[col_idx] - tw - 8, y + 10), text, font=font, fill=hex_color("ink"))
            else:
                draw_wrapped_text(draw, text, (cx + 8, y + 9), widths[col_idx] - 16, font, hex_color("ink"), line_gap=2, max_lines=2)
            cx += widths[col_idx]
        draw.line([table_x, y, table_x + table_w, y], fill=hex_color("line"), width=1)
    if max_rows is not None and len(rows) == max_rows:
        pass


def series_millions(series: pd.Series) -> list[float]:
    """Series를 백만원 리스트로 변환한다."""
    return [float(value) / 1_000_000 for value in series.values]


def draw_line_chart_slide(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    series_dict: dict[str, pd.Series],
    fonts: dict[str, ImageFont.FreeTypeFont],
    unit_label: str = "단위: 백만원",
) -> None:
    """슬라이드용 라인 차트."""
    rounded_card(draw, box)
    x1, y1, x2, y2 = box
    draw.text((x1 + 22, y1 + 18), title, font=fonts["section"], fill=hex_color("ink"))
    draw.text((x2 - 120, y1 + 24), unit_label, font=fonts["body_xs"], fill=hex_color("muted"))
    px1, py1, px2, py2 = x1 + 72, y1 + 80, x2 - 36, y2 - 54
    values_by_name = {name: series_millions(series) for name, series in series_dict.items()}
    labels = list(next(iter(series_dict.values())).index) if series_dict else []
    all_values = [value for values in values_by_name.values() for value in values]
    min_value, max_value = chart_bounds(all_values)
    zero_y = int(scale_y(0, min_value, max_value, py1, py2 - py1))
    draw.line([px1, py2, px2, py2], fill=hex_color("line"), width=2)
    draw.line([px1, py1, px1, py2], fill=hex_color("line"), width=2)
    if py1 <= zero_y <= py2:
        draw.line([px1, zero_y, px2, zero_y], fill="#C8C8C8", width=1)
    palette = [hex_color("red"), hex_color("orange"), hex_color("rose"), "#6A6A6A"]
    for s_idx, (name, values) in enumerate(values_by_name.items()):
        points = []
        for idx, value in enumerate(values):
            x = px1 + int((px2 - px1) * idx / max(len(values) - 1, 1))
            y = int(scale_y(value, min_value, max_value, py1, py2 - py1))
            y = py2 - (y - py1)
            points.append((x, y))
        for p1, p2 in zip(points, points[1:]):
            draw.line([p1, p2], fill=palette[s_idx % len(palette)], width=5)
        for point in points:
            draw.ellipse([point[0] - 6, point[1] - 6, point[0] + 6, point[1] + 6], fill=palette[s_idx % len(palette)])
        draw.rectangle([x1 + 24 + s_idx * 170, y2 - 34, x1 + 44 + s_idx * 170, y2 - 20], fill=palette[s_idx % len(palette)])
        draw.text((x1 + 52 + s_idx * 170, y2 - 38), name, font=fonts["chart_bold"], fill=hex_color("muted"))
    for idx, label in enumerate(labels):
        x = px1 + int((px2 - px1) * idx / max(len(labels) - 1, 1))
        draw.text((x - 20, py2 + 14), str(label).replace("Year ", "Y"), font=fonts["chart"], fill=hex_color("muted"))
    draw.text((x1 + 18, py1 - 4), f"{max_value:,.1f}", font=fonts["chart"], fill=hex_color("muted"))
    draw.text((x1 + 18, py2 - 12), f"{min_value:,.1f}", font=fonts["chart"], fill=hex_color("muted"))


def draw_bar_chart_slide(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    title: str,
    series_dict: dict[str, pd.Series],
    fonts: dict[str, ImageFont.FreeTypeFont],
) -> None:
    """슬라이드용 그룹 막대 차트."""
    rounded_card(draw, box)
    x1, y1, x2, y2 = box
    draw.text((x1 + 22, y1 + 18), title, font=fonts["section"], fill=hex_color("ink"))
    draw.text((x2 - 120, y1 + 24), "단위: 백만원", font=fonts["body_xs"], fill=hex_color("muted"))
    px1, py1, px2, py2 = x1 + 72, y1 + 80, x2 - 36, y2 - 54
    names = list(series_dict.keys())
    labels = list(next(iter(series_dict.values())).index) if series_dict else []
    values_by_name = {name: series_millions(series) for name, series in series_dict.items()}
    all_values = [value for values in values_by_name.values() for value in values]
    min_value, max_value = chart_bounds(all_values)
    zero_y_raw = scale_y(0, min_value, max_value, py1, py2 - py1)
    zero_y = py2 - int(zero_y_raw - py1)
    draw.line([px1, zero_y, px2, zero_y], fill=hex_color("line"), width=2)
    group_w = (px2 - px1) / max(len(labels), 1)
    bar_w = min(28, group_w / max(len(names), 1) * 0.55)
    palette = [hex_color("red"), hex_color("orange"), "#6A6A6A"]
    for idx, label in enumerate(labels):
        center = px1 + group_w * idx + group_w / 2
        for s_idx, name in enumerate(names):
            value = values_by_name[name][idx]
            y_raw = scale_y(value, min_value, max_value, py1, py2 - py1)
            bar_y = py2 - int(y_raw - py1)
            bx = int(center + (s_idx - (len(names) - 1) / 2) * (bar_w + 6) - bar_w / 2)
            draw.rectangle([bx, min(zero_y, bar_y), bx + int(bar_w), max(zero_y, bar_y)], fill=palette[s_idx % len(palette)])
        draw.text((int(center) - 20, py2 + 14), str(label).replace("Year ", "Y"), font=fonts["chart"], fill=hex_color("muted"))
    for s_idx, name in enumerate(names):
        lx = x1 + 24 + s_idx * 170
        draw.rectangle([lx, y2 - 34, lx + 20, y2 - 20], fill=palette[s_idx % len(palette)])
        draw.text((lx + 28, y2 - 38), name, font=fonts["chart_bold"], fill=hex_color("muted"))


def draw_footer(draw: ImageDraw.ImageDraw, page_no: int, fonts: dict[str, ImageFont.FreeTypeFont]) -> None:
    """슬라이드 푸터."""
    draw.line([SLIDE_MARGIN, SLIDE_H - 58, SLIDE_W - SLIDE_MARGIN, SLIDE_H - 58], fill=hex_color("line"), width=2)
    draw.text((SLIDE_MARGIN, SLIDE_H - 42), "Business Profitability Assessment", font=fonts["footer"], fill=hex_color("muted"))
    draw.text((SLIDE_W - SLIDE_MARGIN - 35, SLIDE_H - 42), str(page_no), font=fonts["footer"], fill=hex_color("muted"))

def format_pdf_cell(value: Any) -> str:
    """PDF 표에 넣을 값을 문자열로 정리한다."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    if isinstance(value, float):
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def dataframe_for_pdf(df: pd.DataFrame, max_rows: int | None = None) -> list[list[str]]:
    """DataFrame을 ReportLab 표 데이터로 변환한다."""
    safe_df = df.copy()
    if max_rows is not None:
        safe_df = safe_df.head(max_rows)
    rows = [[str(col) for col in safe_df.columns]]
    for _, row in safe_df.iterrows():
        rows.append([format_pdf_cell(row[col]) for col in safe_df.columns])
    return rows


def pdf_table(rows: list[list[str]], repeat_header: bool = True) -> Table:
    """공통 PDF 표 스타일을 적용한다."""
    table = Table(rows, repeatRows=1 if repeat_header and len(rows) > 1 else 0)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "HYGothic-Medium"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def compact_pdf_table(rows: list[list[str]]) -> Table:
    """요약 페이지용 compact 표 스타일을 적용한다."""
    table = Table(rows)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "HYGothic-Medium"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2D2D2D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7D7D7")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def value_to_millions(value: Any) -> float:
    """차트 표시용으로 금액을 백만원 단위로 변환한다."""
    try:
        return float(value) / 1_000_000
    except (TypeError, ValueError):
        return 0.0


def chart_bounds(values: list[float]) -> tuple[float, float]:
    """차트 축 범위를 계산한다."""
    if not values:
        return 0.0, 1.0
    min_value = min(values)
    max_value = max(values)
    if min_value == max_value:
        padding = abs(max_value) * 0.15 or 1.0
        return min_value - padding, max_value + padding
    padding = (max_value - min_value) * 0.12
    return min(0.0, min_value - padding), max_value + padding


def scale_y(value: float, min_value: float, max_value: float, y: float, height: float) -> float:
    """숫자를 차트 y좌표로 변환한다."""
    if max_value == min_value:
        return y + height / 2
    return y + ((value - min_value) / (max_value - min_value)) * height


def chart_canvas(title: str, width: float = 240, height: float = 145) -> tuple[Drawing, float, float, float, float]:
    """보고서 차트용 캔버스를 만든다."""
    drawing = Drawing(width, height)
    drawing.add(Rect(0, 0, width, height, fillColor=colors.white, strokeColor=colors.HexColor("#D7D7D7"), strokeWidth=0.5))
    drawing.add(Rect(0, height - 18, width, 18, fillColor=colors.HexColor("#2D2D2D"), strokeColor=None))
    drawing.add(String(8, height - 13, title, fontName="HYGothic-Medium", fontSize=8, fillColor=colors.white))
    return drawing, 34, 26, width - 48, height - 52


def line_chart_pdf(title: str, series_dict: dict[str, pd.Series], width: float = 240, height: float = 145) -> Drawing:
    """대시보드 추이 차트를 PDF용 선 그래프로 그린다."""
    palette = [colors.HexColor("#D04A02"), colors.HexColor("#EB8C00"), colors.HexColor("#7D7D7D"), colors.HexColor("#DB536A")]
    drawing, x0, y0, plot_w, plot_h = chart_canvas(title, width, height)
    labels = list(next(iter(series_dict.values())).index) if series_dict else []
    values_by_name = {name: [value_to_millions(v) for v in series.values] for name, series in series_dict.items()}
    all_values = [value for values in values_by_name.values() for value in values]
    min_value, max_value = chart_bounds(all_values)

    drawing.add(Line(x0, y0, x0 + plot_w, y0, strokeColor=colors.HexColor("#B8B8B8"), strokeWidth=0.5))
    drawing.add(Line(x0, y0, x0, y0 + plot_h, strokeColor=colors.HexColor("#B8B8B8"), strokeWidth=0.5))
    if min_value < 0 < max_value:
        zero_y = scale_y(0, min_value, max_value, y0, plot_h)
        drawing.add(Line(x0, zero_y, x0 + plot_w, zero_y, strokeColor=colors.HexColor("#D7D7D7"), strokeWidth=0.4))

    for series_idx, (name, values) in enumerate(values_by_name.items()):
        color = palette[series_idx % len(palette)]
        points: list[tuple[float, float]] = []
        for idx, value in enumerate(values):
            x = x0 + (plot_w * idx / max(len(values) - 1, 1))
            y = scale_y(value, min_value, max_value, y0, plot_h)
            points.append((x, y))
            drawing.add(Circle(x, y, 2, fillColor=color, strokeColor=color))
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            drawing.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=1.4))
        legend_x = x0 + series_idx * 72
        drawing.add(Rect(legend_x, 7, 7, 4, fillColor=color, strokeColor=None))
        drawing.add(String(legend_x + 10, 6, name, fontName="HYGothic-Medium", fontSize=6, fillColor=colors.HexColor("#404040")))

    for idx, label in enumerate(labels):
        x = x0 + (plot_w * idx / max(len(labels) - 1, 1))
        drawing.add(String(x - 10, y0 - 11, str(label).replace("Year ", "Y"), fontName="HYGothic-Medium", fontSize=5.5, fillColor=colors.HexColor("#555555")))
    drawing.add(String(5, y0 + plot_h - 4, f"{max_value:,.0f}M", fontName="HYGothic-Medium", fontSize=5.5, fillColor=colors.HexColor("#555555")))
    drawing.add(String(5, y0 - 2, f"{min_value:,.0f}M", fontName="HYGothic-Medium", fontSize=5.5, fillColor=colors.HexColor("#555555")))
    return drawing


def bar_chart_pdf(title: str, series_dict: dict[str, pd.Series], width: float = 240, height: float = 145) -> Drawing:
    """대시보드 비교 차트를 PDF용 막대 그래프로 그린다."""
    palette = [colors.HexColor("#D04A02"), colors.HexColor("#EB8C00"), colors.HexColor("#7D7D7D")]
    drawing, x0, y0, plot_w, plot_h = chart_canvas(title, width, height)
    labels = list(next(iter(series_dict.values())).index) if series_dict else []
    names = list(series_dict.keys())
    values_by_name = {name: [value_to_millions(v) for v in series.values] for name, series in series_dict.items()}
    all_values = [value for values in values_by_name.values() for value in values]
    min_value, max_value = chart_bounds(all_values)
    zero_y = scale_y(0, min_value, max_value, y0, plot_h)
    drawing.add(Line(x0, zero_y, x0 + plot_w, zero_y, strokeColor=colors.HexColor("#B8B8B8"), strokeWidth=0.6))
    group_w = plot_w / max(len(labels), 1)
    bar_w = min(10, group_w / max(len(names), 1) * 0.65)
    for idx, label in enumerate(labels):
        center = x0 + group_w * idx + group_w / 2
        for series_idx, name in enumerate(names):
            value = values_by_name[name][idx]
            bar_x = center + (series_idx - (len(names) - 1) / 2) * (bar_w + 2) - bar_w / 2
            bar_y = scale_y(value, min_value, max_value, y0, plot_h)
            rect_y = min(zero_y, bar_y)
            rect_h = max(abs(bar_y - zero_y), 1)
            drawing.add(Rect(bar_x, rect_y, bar_w, rect_h, fillColor=palette[series_idx % len(palette)], strokeColor=None))
        drawing.add(String(center - 8, y0 - 11, str(label).replace("Year ", "Y"), fontName="HYGothic-Medium", fontSize=5.5, fillColor=colors.HexColor("#555555")))
    for series_idx, name in enumerate(names):
        legend_x = x0 + series_idx * 72
        drawing.add(Rect(legend_x, 7, 7, 4, fillColor=palette[series_idx % len(palette)], strokeColor=None))
        drawing.add(String(legend_x + 10, 6, name, fontName="HYGothic-Medium", fontSize=6, fillColor=colors.HexColor("#404040")))
    return drawing


def horizontal_bar_pdf(title: str, labels: list[str], values: list[float], width: float = 240, height: float = 145) -> Drawing:
    """비용 구성 차트를 PDF용 가로 막대로 그린다."""
    drawing, x0, y0, plot_w, plot_h = chart_canvas(title, width, height)
    max_value = max(values) if values else 1.0
    row_h = plot_h / max(len(values), 1)
    for idx, (label, value) in enumerate(zip(labels, values)):
        y = y0 + plot_h - (idx + 1) * row_h + row_h * 0.25
        bar_w = (value / max_value) * (plot_w * 0.58) if max_value else 0
        drawing.add(String(x0, y + 2, str(label)[:14], fontName="HYGothic-Medium", fontSize=5.5, fillColor=colors.HexColor("#404040")))
        drawing.add(Rect(x0 + 82, y, bar_w, max(row_h * 0.45, 4), fillColor=colors.HexColor("#D04A02"), strokeColor=None))
        drawing.add(String(x0 + 86 + bar_w, y + 1, f"{value_to_millions(value):,.0f}M", fontName="HYGothic-Medium", fontSize=5.2, fillColor=colors.HexColor("#555555")))
    return drawing


def chart_grid(charts: list[Drawing]) -> Table:
    """PDF 차트를 2열 그리드로 배치한다."""
    rows = []
    for idx in range(0, len(charts), 2):
        row = charts[idx : idx + 2]
        if len(row) == 1:
            row.append(Drawing(240, 145))
        rows.append(row)
    table = Table(rows, colWidths=[250, 250])
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return table


def report_section(story: list[Any], title: str, rows: list[list[str]], styles: dict[str, ParagraphStyle]) -> None:
    """PDF 보고서 섹션을 추가한다."""
    story.append(Paragraph(title, styles["section"]))
    story.append(pdf_table(rows))
    story.append(Spacer(1, 7 * mm))


def build_pdf_report(
    assumptions: dict[str, Any],
    revenue_df: pd.DataFrame,
    cost_df: pd.DataFrame,
    staffing_df: pd.DataFrame,
    model_result: dict[str, Any],
    currency: str,
) -> bytes:
    """입력값과 결과 대시보드를 16:9 발표형 PDF 보고서로 생성한다."""
    fonts = load_slide_fonts()
    initial = assumptions.get("initial_investment", {})
    pages: list[Image.Image] = []
    kpis = model_result["kpis"]

    # Page 1: Cover
    page = Image.new("RGB", (SLIDE_W, SLIDE_H), hex_color("bg"))
    draw = ImageDraw.Draw(page)
    draw.rectangle([0, 0, SLIDE_W, SLIDE_H], fill=hex_color("bg"))
    draw.rectangle([0, 0, 470, SLIDE_H], fill=hex_color("dark"))
    draw.rectangle([0, 0, 470, 260], fill=hex_color("red"))
    draw.rectangle([470, 0, 690, 260], fill=hex_color("orange"))
    draw.rectangle([690, 0, 820, 260], fill=hex_color("yellow"))
    draw.text((92, 410), "Business\nProfitability\nReport", font=fonts["title"], fill="#FFFFFF", spacing=12)
    draw.text((590, 345), "사업 수익성 분석 보고서", font=ImageFont.truetype(str(FONT_DIR / "Pretendard-Bold.otf"), 74), fill=hex_color("ink"))
    draw_wrapped_text(draw, "현재 입력값과 결과 대시보드를 바탕으로 작성된 투자검토용 요약 보고서입니다.", (596, 458), 980, fonts["subtitle"], hex_color("muted"), line_gap=10, max_lines=2)
    meta = [
        ["사업명", str(assumptions.get("business_name", ""))],
        ["업종", str(assumptions.get("industry", ""))],
        ["분석기간", f"{assumptions.get('analysis_years', '')}년"],
        ["기준 통화", str(assumptions.get("currency", "KRW"))],
    ]
    draw_small_table(draw, (596, 600, 1590, 820), "Report Scope", ["구분", "내용"], meta, [0.25, 0.75], fonts)
    draw.text((596, 900), "Prepared for decision review", font=fonts["body"], fill=hex_color("muted"))
    draw_footer(draw, 1, fonts)
    pages.append(page)

    # Page 2: Executive Summary & Key KPI
    page, draw = make_slide("Executive Summary & Key KPI", "핵심 숫자와 의사결정 포인트", 2, fonts)
    kpi_items = [
        ("총매출", format_million(kpis["총매출"]), "분석기간 누적 매출", "red"),
        ("영업이익", format_million(kpis["영업이익"]), "총비용 차감 후 영업성과", "orange"),
        ("순이익", format_million(kpis["순이익"]), "세금 반영 후 최종 이익", "red"),
        ("영업이익률", pct_display(kpis["영업이익률"]), "누적 매출 대비", "orange"),
        ("투자회수기간", str(kpis["투자회수기간"]), "누적현금흐름 기준", "red"),
        ("ROI", pct_display(kpis["ROI"]), "초기투자비 대비 5년 누적 순이익", "orange"),
    ]
    for idx, item in enumerate(kpi_items):
        x = SLIDE_MARGIN + (idx % 3) * 580
        y = 178 + (idx // 3) * 178
        label, value, note, accent = item
        draw_kpi_card(draw, (x, y, x + 532, y + 138), label, value, note, fonts, accent)
    decision_y = 590
    rounded_card(draw, (SLIDE_MARGIN, decision_y, SLIDE_W - SLIDE_MARGIN, 885))
    draw.text((SLIDE_MARGIN + 28, decision_y + 26), "Decision Readout", font=fonts["section"], fill=hex_color("ink"))
    margin_ratio = float(kpis["영업이익률"])
    roi = float(kpis["ROI"])
    payback = str(kpis["투자회수기간"])
    bullets = [
        f"영업이익률은 {pct_display(margin_ratio)}로 추정됩니다.",
        f"ROI는 {pct_display(roi)}이며, 초기투자비 대비 누적 순이익 기준입니다.",
        f"투자회수기간은 {payback}입니다.",
        f"손익분기매출(1년차)은 {format_million(kpis['손익분기매출(1년차)'])}입니다.",
    ]
    for idx, bullet in enumerate(bullets):
        y = decision_y + 82 + idx * 44
        draw.ellipse([SLIDE_MARGIN + 32, y + 6, SLIDE_MARGIN + 44, y + 18], fill=hex_color("red"))
        draw_wrapped_text(draw, bullet, (SLIDE_MARGIN + 60, y), 1450, fonts["body"], hex_color("ink"), max_lines=1)
    pages.append(page)

    # Page 3: Input Assumptions Summary 1
    page, draw = make_slide("Input Assumptions Summary 1", "기본설정, 성장률, 초기투자비", 3, fonts)
    basic_rows = [
        ["사업명", assumptions.get("business_name", "")],
        ["업종", assumptions.get("industry", "")],
        ["분석기간", f"{assumptions.get('analysis_years', '')}년"],
        ["기준통화", assumptions.get("currency", "KRW")],
        ["세율", pct_display(assumptions.get("tax_rate_pct", 0), already_percent=True)],
    ]
    growth_rows = [
        ["매출 성장률", pct_display(assumptions.get("revenue_growth_pct", 0), already_percent=True)],
        ["비용 증가율", pct_display(assumptions.get("cost_growth_pct", 0), already_percent=True)],
        ["인건비 증가율", pct_display(assumptions.get("labor_growth_pct", 0), already_percent=True)],
        ["임대료 증가율", pct_display(assumptions.get("rent_growth_pct", 0), already_percent=True)],
        ["기타 비용 증가율", pct_display(assumptions.get("other_growth_pct", 0), already_percent=True)],
    ]
    investment_rows = [[key, format_million(initial.get(key, 0))] for key in INITIAL_INVESTMENT_KEYS]
    investment_rows.append(["합계", format_million(sum(float(initial.get(key, 0)) for key in INITIAL_INVESTMENT_KEYS))])
    draw_small_table(draw, (92, 170, 650, 515), "기본 설정", ["항목", "값"], basic_rows, [0.42, 0.58], fonts)
    draw_small_table(draw, (700, 170, 1260, 515), "성장률", ["항목", "값"], growth_rows, [0.58, 0.42], fonts)
    draw_small_table(draw, (1310, 170, 1828, 770), "초기투자비 (단위: 백만원)", ["항목", "금액"], investment_rows, [0.58, 0.42], fonts, money_cols={1}, highlight_rows={len(investment_rows) - 1})
    draw_wrapped_text(draw, "초기투자비는 보증금, 인테리어, 설비/장비, 초기재고 및 인허가/컨설팅 비용을 합산한 투자 전제입니다.", (92, 610), 1110, fonts["body"], hex_color("muted"), max_lines=3)
    pages.append(page)

    # Page 4: Input Assumptions Summary 2
    page, draw = make_slide("Input Assumptions Summary 2", "핵심 입력 요약: 매출, 비용, 인력", 4, fonts)
    rev_rows = []
    for _, row in revenue_df.iterrows():
        rev_rows.append([row["매출항목명"], row["계산방식"], format_million(row["단가"], ""), format_number_1(row["수량/이용자수"]), row["발생주기"], pct_display(row["연간성장률(%)"], already_percent=True)])
    cost_rows = []
    for _, row in cost_df.iterrows():
        cost_rows.append([row["비용항목명"], row["비용유형"], format_million(row["월비용"], ""), format_million(row["연비용"], ""), pct_display(row["매출대비비율(%)"], already_percent=True), pct_display(row["연간증가율(%)"], already_percent=True)])
    staff_rows = []
    for _, row in staffing_df.iterrows():
        staff_rows.append([row["직무명"], format_number_1(row["인원수"]), format_million(row["1인당월급"], ""), pct_display(row["4대보험/복리후생비율(%)"], already_percent=True), pct_display(row["연봉상승률(%)"], already_percent=True), pct_display(row["연간인원증가율(%)"], already_percent=True)])
    draw_small_table(draw, (92, 158, 1828, 390), "매출 입력 핵심 요약 (금액 단위: 백만원)", ["항목명", "계산방식", "단가", "수량/이용자", "주기", "성장률"], rev_rows, [0.24, 0.24, 0.12, 0.13, 0.09, 0.10], fonts, money_cols={2}, max_rows=4)
    draw_small_table(draw, (92, 420, 1828, 678), "비용 입력 핵심 요약 (금액 단위: 백만원)", ["항목명", "유형", "월비용", "연비용", "매출대비", "증가율"], cost_rows, [0.28, 0.16, 0.14, 0.14, 0.12, 0.12], fonts, money_cols={2, 3}, max_rows=6)
    draw_small_table(draw, (92, 708, 1828, 930), "인력 입력 핵심 요약 (금액 단위: 백만원)", ["직무명", "인원", "월급", "복리후생", "연봉상승", "인원증가"], staff_rows, [0.28, 0.12, 0.16, 0.15, 0.15, 0.14], fonts, money_cols={2}, max_rows=4)
    pages.append(page)

    # Page 5: Dashboard View
    page, draw = make_slide("Dashboard View", "핵심 숫자 → 추세 → 의사결정 포인트", 5, fonts)
    dashboard_items = [
        ("총매출", format_million(kpis["총매출"]), "누적", "red"),
        ("영업이익", format_million(kpis["영업이익"]), "누적", "orange"),
        ("순이익", format_million(kpis["순이익"]), "누적", "red"),
        ("영업이익률", pct_display(kpis["영업이익률"]), "수익성", "orange"),
        ("투자회수", str(kpis["투자회수기간"]), "Payback", "red"),
        ("손익분기매출", format_million(kpis["손익분기매출(1년차)"]), "Year 1", "orange"),
    ]
    for idx, item in enumerate(dashboard_items):
        x = 92 + idx * 292
        label, value, note, accent = item
        draw_kpi_card(draw, (x, 148, x + 264, 278), label, value, note, fonts, accent)
    draw_line_chart_slide(draw, (92, 320, 920, 610), "연도별 매출 추이", {"총매출": model_result["series"]["revenue"]}, fonts)
    draw_line_chart_slide(draw, (1000, 320, 1828, 610), "연도별 비용 추이", {"총비용": model_result["series"]["total_cost"]}, fonts)
    draw_bar_chart_slide(draw, (92, 650, 920, 940), "영업이익 및 순이익 추이", {"영업이익": model_result["series"]["operating_income"], "순이익": model_result["series"]["net_income"]}, fonts)
    draw_line_chart_slide(draw, (1000, 650, 1828, 940), "누적 현금흐름", {"누적현금흐름": model_result["series"]["cumulative_cash_flow"]}, fonts)
    pages.append(page)

    # Page 6: Profit & Loss Statement
    page, draw = make_slide("Profit & Loss Statement", "손익계산서: 연도별 추정치, 단위: 백만원", 6, fonts)
    pnl = model_result["pnl"].copy()
    years = [col for col in pnl.columns if str(col).startswith("Year")]
    pnl_rows = []
    highlight_names = {"총매출", "매출총이익", "EBITDA", "영업이익", "순이익", "누적 순이익", "영업이익률", "순이익률"}
    highlight_rows = set()
    for idx, row in pnl.iterrows():
        name = row["항목"]
        values = []
        for year in years:
            values.append(pct_display(row[year]) if "률" in str(name) else format_million(row[year], ""))
        if name in highlight_names:
            highlight_rows.add(len(pnl_rows))
        pnl_rows.append([name, *values])
    draw_small_table(draw, (92, 160, 1828, 880), "손익계산서 (단위: 백만원, 비율: %)", ["항목", *years], pnl_rows, [0.24, 0.152, 0.152, 0.152, 0.152, 0.152], fonts, money_cols={1, 2, 3, 4, 5}, highlight_rows=highlight_rows)
    draw_wrapped_text(draw, "강조 행은 수익성 판단에 직접 영향을 주는 핵심 계정입니다. 금액은 원 단위가 아닌 백만원 단위로 환산했습니다.", (92, 905), 1500, fonts["body"], hex_color("muted"), max_lines=2)
    pages.append(page)

    # Page 7: Cash Flow & Payback Analysis
    page, draw = make_slide("Cash Flow & Payback Analysis", "현금흐름표: Year 0 포함, 단위: 백만원", 7, fonts)
    cash_df = model_result["cash_flow"].copy()
    cash_rows = []
    positive_cross = None
    for idx, row in cash_df.iterrows():
        flow = float(row["현금흐름"])
        cumulative = float(row["누적현금흐름"])
        if positive_cross is None and row["연도"] != "Year 0" and cumulative >= 0:
            positive_cross = idx
        cash_rows.append([row["연도"], format_million(flow, ""), format_million(cumulative, "")])
    highlight = {0}
    if positive_cross is not None:
        highlight.add(positive_cross)
    draw_small_table(draw, (92, 170, 840, 720), "현금흐름표 (단위: 백만원)", ["연도", "현금흐름", "누적현금흐름"], cash_rows, [0.28, 0.36, 0.36], fonts, money_cols={1, 2}, highlight_rows=highlight)
    draw_line_chart_slide(draw, (920, 170, 1828, 720), "누적현금흐름 추이", {"누적현금흐름": model_result["series"]["cumulative_cash_flow"]}, fonts)
    rounded_card(draw, (92, 760, 1828, 910))
    draw.text((120, 790), "Payback Insight", font=fonts["section"], fill=hex_color("ink"))
    payback_text = f"투자회수기간은 {kpis['투자회수기간']}입니다. Year 0의 초기투자비를 반영한 누적현금흐름이 양수로 전환되는 시점을 기준으로 판단합니다."
    draw_wrapped_text(draw, payback_text, (120, 838), 1580, fonts["body"], hex_color("ink"), max_lines=2)
    pages.append(page)

    # Page 8: Break-even Analysis
    page, draw = make_slide("Break-even Analysis", "손익분기점 및 안전마진 분석, 금액 단위: 백만원", 8, fonts)
    break_rows = []
    revenue_series = model_result["series"]["revenue"]
    for _, row in model_result["break_even"].iterrows():
        year = row["연도"]
        expected = float(revenue_series.get(year, 0))
        be_sales = float(row["손익분기매출"])
        excess = expected - be_sales
        safety = excess / expected if expected else 0
        break_rows.append(
            [
                year,
                format_million(expected, ""),
                format_million(be_sales, ""),
                format_million(excess, ""),
                pct_display(safety),
                pct_display(row["공헌이익률"]),
                format_number_1(row["손익분기판매량"]),
            ]
        )
    draw_small_table(draw, (92, 170, 1828, 640), "손익분기점 비교표 (금액 단위: 백만원)", ["연도", "예상매출", "손익분기매출", "초과매출", "안전마진율", "공헌이익률", "손익분기판매량"], break_rows, [0.10, 0.15, 0.17, 0.15, 0.14, 0.14, 0.15], fonts, money_cols={1, 2, 3})
    break_even_series = pd.Series({row["연도"]: row["손익분기매출"] for _, row in model_result["break_even"].iterrows()}, name="손익분기 매출")
    draw_line_chart_slide(draw, (92, 690, 920, 940), "예상매출 vs 손익분기매출", {"예상 매출": model_result["series"]["revenue"], "손익분기 매출": break_even_series}, fonts)
    rounded_card(draw, (1000, 690, 1828, 940))
    draw.text((1028, 720), "Decision Point", font=fonts["section"], fill=hex_color("ink"))
    draw_wrapped_text(draw, "예상매출이 손익분기매출을 안정적으로 초과하면 고정비 부담을 흡수할 여지가 커집니다. 안전마진율이 낮은 연도는 가격, 판매량, 원가율 조정이 필요한 구간입니다.", (1028, 772), 730, fonts["body"], hex_color("ink"), max_lines=4)
    pages.append(page)

    output = BytesIO()
    pages[0].save(output, format="PDF", save_all=True, append_images=pages[1:], resolution=150.0)
    return output.getvalue()

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

    input_tab, dashboard_tab, pdf_tab = st.tabs(["① 입력", "② 결과 대시보드", "③ PDF 보고서"])

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

    with pdf_tab:
        st.subheader("PDF 보고서 추출")
        st.caption("현재 입력값, 핵심 KPI, 대시보드 차트, 손익표를 전문 보고서 형식의 PDF로 저장합니다.")
        pdf_bytes = build_pdf_report(
            assumptions,
            st.session_state["revenue_df"],
            st.session_state["cost_df"],
            st.session_state["staffing_df"],
            model_result,
            currency,
        )
        st.download_button(
            "PDF 보고서 다운로드",
            data=pdf_bytes,
            file_name=pdf_filename(assumptions),
            mime="application/pdf",
            use_container_width=True,
        )
        st.markdown(
            """
            포함 항목:
            - 기본 설정, 성장률, 초기투자비
            - 매출 입력, 비용 입력, 인력 입력
            - 핵심 KPI, 대시보드 차트, 손익계산서, 현금흐름, 손익분기점
            """
        )


if __name__ == "__main__":
    main()
