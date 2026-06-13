"""Vector/text based PDF report generator for the Streamlit MVP."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


BASE_DIR = Path(__file__).resolve().parent
FONT_DIR = BASE_DIR / "assets" / "fonts"


PAGE_W, PAGE_H = landscape(A4)
MARGIN = 42


PALETTE = {
    "bg": "#F7F5F2",
    "paper": "#FFFFFF",
    "ink": "#242424",
    "muted": "#666666",
    "line": "#D8D2CB",
    "dark": "#2D2D2D",
    "red": "#D04A02",
    "orange": "#EB8C00",
    "yellow": "#FFB600",
    "rose": "#DB536A",
    "green": "#2E7D32",
    "blue": "#2F6B9A",
}
CHART_COLORS = [PALETTE["red"], PALETTE["orange"], PALETTE["blue"], PALETTE["green"], PALETTE["rose"]]


def register_fonts() -> None:
    # Pretendard Std TTF does not include Hangul glyphs. Use the full variable
    # Pretendard TTF so ReportLab can embed Korean text without tofu/broken glyphs.
    variable_font = FONT_DIR / "PretendardVariable.ttf"
    if "PretendardPDF" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("PretendardPDF", str(variable_font)))


def money_m(value: Any, suffix: str = "백만원") -> str:
    try:
        number = float(value) / 1_000_000
    except (TypeError, ValueError):
        number = 0.0
    return f"{number:,.1f} {suffix}" if suffix else f"{number:,.1f}"


def number_1(value: Any) -> str:
    try:
        return f"{float(value):,.1f}"
    except (TypeError, ValueError):
        return str(value)


def pct_point(value: Any) -> str:
    try:
        return f"{float(value):,.1f}%"
    except (TypeError, ValueError):
        return str(value)


def pct_ratio(value: Any) -> str:
    try:
        return f"{float(value) * 100:,.1f}%"
    except (TypeError, ValueError):
        return str(value)


class ReportPainter:
    def __init__(self, pdf: canvas.Canvas):
        self.pdf = pdf

    def fill(self, hex_color: str) -> None:
        self.pdf.setFillColor(colors.HexColor(hex_color))

    def stroke(self, hex_color: str, line_width: float = 1) -> None:
        self.pdf.setStrokeColor(colors.HexColor(hex_color))
        self.pdf.setLineWidth(line_width)

    def text_width(self, text: str, font: str, size: float) -> float:
        return pdfmetrics.stringWidth(str(text), font, size)

    def text(
        self,
        value: Any,
        x: float,
        y: float,
        size: float = 10,
        font: str = "PretendardPDF",
        color: str = "ink",
        align: str = "left",
    ) -> None:
        text = str(value)
        self.fill(PALETTE[color])
        self.pdf.setFont(font, size)
        if align == "right":
            x -= self.text_width(text, font, size)
        elif align == "center":
            x -= self.text_width(text, font, size) / 2
        self.pdf.drawString(x, y, text)

    def wrap_lines(self, value: Any, max_width: float, font: str, size: float, max_lines: int | None = None) -> list[str]:
        words = str(value).replace("\n", " ").split()
        if not words:
            return [""]
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if self.text_width(candidate, font, size) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
            while lines[-1] and self.text_width(lines[-1] + "...", font, size) > max_width:
                lines[-1] = lines[-1][:-1]
            lines[-1] += "..."
        return lines

    def wrapped(
        self,
        value: Any,
        x: float,
        y: float,
        max_width: float,
        size: float = 10,
        font: str = "PretendardPDF",
        color: str = "ink",
        leading: float = 1.35,
        max_lines: int | None = None,
    ) -> float:
        lines = self.wrap_lines(value, max_width, font, size, max_lines=max_lines)
        for idx, line in enumerate(lines):
            self.text(line, x, y - idx * size * leading, size, font, color)
        return y - len(lines) * size * leading

    def card(self, x: float, y: float, w: float, h: float, bg: str = "paper", border: str = "line") -> None:
        self.fill(PALETTE[bg])
        self.stroke(PALETTE[border], 0.8)
        self.pdf.roundRect(x, y, w, h, 6, fill=1, stroke=1)

    def footer(self, page_no: int) -> None:
        self.stroke(PALETTE["line"], 0.6)
        self.pdf.line(MARGIN, 28, PAGE_W - MARGIN, 28)
        self.text("Business Profitability Assessment", MARGIN, 14, 8.8, "PretendardPDF", "muted")
        self.text(str(page_no), PAGE_W - MARGIN, 14, 8.8, "PretendardPDF", "muted", align="right")

    def page_header(self, title: str, subtitle: str, page_no: int) -> None:
        self.fill(PALETTE["bg"])
        self.pdf.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        self.text(title, MARGIN, PAGE_H - 56, 22, "PretendardPDF", "ink")
        if subtitle:
            self.text(subtitle, MARGIN, PAGE_H - 78, 10.8, "PretendardPDF", "muted")
        self.fill(PALETTE["red"])
        self.pdf.rect(MARGIN, PAGE_H - 88, 56, 3, fill=1, stroke=0)
        self.fill(PALETTE["orange"])
        self.pdf.rect(MARGIN + 58, PAGE_H - 88, 36, 3, fill=1, stroke=0)
        self.footer(page_no)

    def kpi_card(self, x: float, y: float, w: float, h: float, label: str, value: str, note: str, accent: str = "red") -> None:
        self.card(x, y, w, h)
        self.fill(PALETTE[accent])
        self.pdf.roundRect(x, y, 5, h, 3, fill=1, stroke=0)
        self.text(label, x + 16, y + h - 21, 9.4, "PretendardPDF", "muted")
        self.text(value, x + 16, y + h - 48, 18.6, "PretendardPDF", "ink")
        if h >= 66:
            self.wrapped(note, x + 16, y + 8, w - 28, 8.2, "PretendardPDF", "muted", max_lines=1)

    def table(
        self,
        x: float,
        y_top: float,
        w: float,
        title: str,
        headers: list[str],
        rows: list[list[Any]],
        col_fracs: list[float],
        row_h: float = 24,
        header_h: float = 26,
        title_h: float = 30,
        size: float = 9.2,
        highlight_rows: set[int] | None = None,
        right_cols: set[int] | None = None,
        max_rows: int | None = None,
    ) -> float:
        highlight_rows = highlight_rows or set()
        right_cols = right_cols or set()
        shown_rows = rows[:max_rows] if max_rows else rows
        h = title_h + header_h + row_h * max(len(shown_rows), 1)
        y = y_top - h
        self.card(x, y, w, h)
        self.text(title, x + 12, y_top - 20, 10.6, "PretendardPDF", "ink")
        total = sum(col_fracs)
        col_w = [w * frac / total for frac in col_fracs]
        lefts = [x]
        for cw in col_w[:-1]:
            lefts.append(lefts[-1] + cw)
        header_y = y_top - title_h - header_h
        self.fill("#F0ECE8")
        self.pdf.rect(x, header_y, w, header_h, fill=1, stroke=0)
        self.stroke(PALETTE["line"], 0.6)
        self.pdf.line(x, header_y, x + w, header_y)
        for idx, head in enumerate(headers):
            if idx in right_cols:
                self.text(head, lefts[idx] + col_w[idx] - 8, header_y + 9, 8.9, "PretendardPDF", "ink", align="right")
            else:
                self.text(head, lefts[idx] + 8, header_y + 9, 8.9, "PretendardPDF", "ink")
        for row_idx, row in enumerate(shown_rows):
            row_y = header_y - row_h * (row_idx + 1)
            if row_idx in highlight_rows:
                self.fill("#FFF2E8")
                self.pdf.rect(x, row_y, w, row_h, fill=1, stroke=0)
            elif row_idx % 2 == 1:
                self.fill("#FBFAF8")
                self.pdf.rect(x, row_y, w, row_h, fill=1, stroke=0)
            self.stroke(PALETTE["line"], 0.45)
            self.pdf.line(x, row_y, x + w, row_y)
            for col_idx, cell in enumerate(row[: len(headers)]):
                font = "PretendardPDF"
                cell_text = str(cell)
                max_text_w = col_w[col_idx] - 14
                if col_idx in right_cols:
                    while self.text_width(cell_text, font, size) > max_text_w and len(cell_text) > 4:
                        cell_text = cell_text[:-2] + "..."
                    self.text(cell_text, lefts[col_idx] + col_w[col_idx] - 8, row_y + 8, size, font, "ink", align="right")
                else:
                    lines = self.wrap_lines(cell_text, max_text_w, font, size, max_lines=2)
                    for line_no, line in enumerate(lines):
                        self.text(line, lefts[col_idx] + 8, row_y + row_h - 11 - line_no * (size + 1), size, font, "ink")
        if max_rows and len(rows) > max_rows:
            self.text(f"외 {len(rows) - max_rows}개 항목", x + w - 12, y + 8, 8.2, "PretendardPDF", "muted", align="right")
        return y

    def chart_frame(self, x: float, y: float, w: float, h: float, title: str, unit: str = "단위: 백만원") -> tuple[float, float, float, float]:
        self.card(x, y, w, h)
        self.text(title, x + 14, y + h - 22, 10.8, "PretendardPDF", "ink")
        self.text(unit, x + w - 14, y + h - 21, 8.8, "PretendardPDF", "muted", align="right")
        return x + 46, y + 42, w - 70, h - 84

    def axis_bounds(self, values: list[float]) -> tuple[float, float]:
        if not values:
            return 0.0, 1.0
        v_min, v_max = min(values), max(values)
        if v_min == v_max:
            pad = max(abs(v_max) * 0.15, 1.0)
            return v_min - pad, v_max + pad
        pad = (v_max - v_min) * 0.18
        return v_min - pad, v_max + pad

    def line_chart(self, x: float, y: float, w: float, h: float, title: str, series_dict: dict[str, pd.Series]) -> None:
        px, py, pw, ph = self.chart_frame(x, y, w, h, title)
        labels: list[str] = []
        all_values: list[float] = []
        for series in series_dict.values():
            labels = [str(idx) for idx in series.index]
            all_values.extend([float(v) / 1_000_000 for v in series.tolist()])
        y_min, y_max = self.axis_bounds(all_values)
        self.stroke(PALETTE["line"], 0.6)
        for i in range(4):
            gy = py + ph * i / 3
            self.pdf.line(px, gy, px + pw, gy)
            label = y_min + (y_max - y_min) * i / 3
            self.text(f"{label:,.0f}", px - 7, gy - 3, 8.3, "PretendardPDF", "muted", align="right")
        for i, label in enumerate(labels):
            tx = px + pw * i / max(len(labels) - 1, 1)
            self.text(label, tx, py - 18, 8.5, "PretendardPDF", "muted", align="center")
        for series_idx, (name, series) in enumerate(series_dict.items()):
            values = [float(v) / 1_000_000 for v in series.tolist()]
            points = []
            for i, value in enumerate(values):
                tx = px + pw * i / max(len(values) - 1, 1)
                ty = py + ((value - y_min) / (y_max - y_min)) * ph
                points.append((tx, ty, value))
            color = CHART_COLORS[series_idx % len(CHART_COLORS)]
            self.stroke(color, 2.1)
            for p1, p2 in zip(points, points[1:]):
                self.pdf.line(p1[0], p1[1], p2[0], p2[1])
            self.fill(color)
            for tx, ty, value in points:
                self.pdf.circle(tx, ty, 3, fill=1, stroke=0)
                self.text(f"{value:,.0f}", tx, ty + 8, 7.6, "PretendardPDF", "ink", align="center")
            lx = x + 14 + series_idx * 92
            self.fill(color)
            self.pdf.rect(lx, y + h - 41, 8, 8, fill=1, stroke=0)
            self.text(name, lx + 12, y + h - 40, 8.8, "PretendardPDF", "muted")

    def bar_chart(self, x: float, y: float, w: float, h: float, title: str, series_dict: dict[str, pd.Series]) -> None:
        px, py, pw, ph = self.chart_frame(x, y, w, h, title)
        labels = [str(idx) for idx in next(iter(series_dict.values())).index]
        values = [float(v) / 1_000_000 for series in series_dict.values() for v in series.tolist()]
        y_min, y_max = self.axis_bounds(values + [0])
        y_min = min(y_min, 0)
        zero_y = py + ((0 - y_min) / (y_max - y_min)) * ph
        self.stroke(PALETTE["line"], 0.6)
        self.pdf.line(px, zero_y, px + pw, zero_y)
        group_w = pw / max(len(labels), 1)
        series_count = len(series_dict)
        bar_w = min(18, group_w / max(series_count + 1, 2))
        for i, label in enumerate(labels):
            self.text(label, px + group_w * i + group_w / 2, py - 18, 8.5, "PretendardPDF", "muted", align="center")
        for s_idx, (name, series) in enumerate(series_dict.items()):
            color = CHART_COLORS[s_idx % len(CHART_COLORS)]
            self.fill(color)
            for i, raw in enumerate(series.tolist()):
                value = float(raw) / 1_000_000
                cx = px + group_w * i + group_w / 2
                bx = cx - (series_count * bar_w) / 2 + s_idx * bar_w
                by = py + ((value - y_min) / (y_max - y_min)) * ph
                self.pdf.rect(bx, min(zero_y, by), bar_w * 0.78, abs(by - zero_y), fill=1, stroke=0)
                self.text(f"{value:,.0f}", bx + bar_w * 0.39, max(zero_y, by) + 6, 7.5, "PretendardPDF", "ink", align="center")
            lx = x + 14 + s_idx * 92
            self.pdf.rect(lx, y + h - 41, 8, 8, fill=1, stroke=0)
            self.text(name, lx + 12, y + h - 40, 8.8, "PretendardPDF", "muted")


def build_pdf_report(
    assumptions: dict[str, Any],
    revenue_df: pd.DataFrame,
    cost_df: pd.DataFrame,
    staffing_df: pd.DataFrame,
    model_result: dict[str, Any],
    currency: str,
) -> bytes:
    register_fonts()
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=(PAGE_W, PAGE_H))
    pdf.setTitle(f"{assumptions.get('business_name', '사업')} 사업 수익성 분석 보고서")
    pdf.setAuthor("Business Profitability MVP")
    p = ReportPainter(pdf)
    kpis = model_result["kpis"]
    initial = assumptions.get("initial_investment", {})

    # Page 1: Cover
    p.fill(PALETTE["bg"])
    pdf.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    p.fill(PALETTE["dark"])
    pdf.rect(0, 0, 285, PAGE_H, fill=1, stroke=0)
    p.fill(PALETTE["red"])
    pdf.rect(0, PAGE_H - 132, 285, 132, fill=1, stroke=0)
    p.fill(PALETTE["orange"])
    pdf.rect(285, PAGE_H - 132, 60, 132, fill=1, stroke=0)
    p.text("Business", 54, 350, 27, "PretendardPDF", "paper")
    p.text("Profitability", 54, 315, 27, "PretendardPDF", "paper")
    p.text("Report", 54, 280, 27, "PretendardPDF", "paper")
    p.text("사업 수익성 분석 보고서", 360, 372, 29, "PretendardPDF", "ink")
    p.wrapped("현재 입력값과 결과 대시보드를 바탕으로 작성된 투자검토용 요약 보고서입니다.", 364, 336, 420, 12.2, "PretendardPDF", "muted", max_lines=2)
    meta = [
        ["사업명", assumptions.get("business_name", "")],
        ["업종", assumptions.get("industry", "")],
        ["분석기간", f"{assumptions.get('analysis_years', '')}년"],
        ["기준 통화", assumptions.get("currency", "KRW")],
    ]
    p.table(364, 282, 392, "Report Scope", ["구분", "내용"], meta, [0.28, 0.72], row_h=28, size=10.2)
    p.text("Prepared for decision review", 364, 92, 10.5, "PretendardPDF", "muted")
    p.footer(1)
    pdf.showPage()

    # Page 2: Executive Summary
    p.page_header("Executive Summary & Key KPI", "핵심 숫자와 의사결정 포인트", 2)
    kpi_items = [
        ("총매출", money_m(kpis["총매출"]), "분석기간 누적 매출", "red"),
        ("영업이익", money_m(kpis["영업이익"]), "총비용 차감 후 영업성과", "orange"),
        ("순이익", money_m(kpis["순이익"]), "세금 반영 후 최종 이익", "red"),
        ("영업이익률", pct_ratio(kpis["영업이익률"]), "누적 매출 대비", "orange"),
        ("투자회수기간", str(kpis["투자회수기간"]), "누적현금흐름 기준", "red"),
        ("ROI", pct_ratio(kpis["ROI"]), "5년 누적 순이익 / 초기투자비", "orange"),
    ]
    for idx, item in enumerate(kpi_items):
        p.kpi_card(MARGIN + (idx % 3) * 256, 386 - (idx // 3) * 86, 234, 68, *item)
    p.card(MARGIN, 102, PAGE_W - MARGIN * 2, 155)
    p.text("Decision Readout", MARGIN + 18, 226, 14, "PretendardPDF", "ink")
    bullets = [
        f"영업이익률은 {pct_ratio(kpis['영업이익률'])}로 추정됩니다. 누적 영업이익 / 누적 매출 기준입니다.",
        f"ROI는 {pct_ratio(kpis['ROI'])}이며, 초기투자비 대비 5년 누적 순이익 기준입니다.",
        f"투자회수기간은 {kpis['투자회수기간']}입니다.",
        f"1년차 손익분기매출은 {money_m(kpis['손익분기매출(1년차)'])}입니다.",
    ]
    for idx, bullet in enumerate(bullets):
        p.fill(PALETTE["red"])
        pdf.circle(MARGIN + 23, 196 - idx * 26, 2.4, fill=1, stroke=0)
        p.wrapped(bullet, MARGIN + 34, 192 - idx * 26, PAGE_W - MARGIN * 2 - 64, 10.8, "PretendardPDF", "ink", max_lines=1)
    pdf.showPage()

    # Page 3: Input Summary 1
    p.page_header("Input Assumptions Summary 1", "기본설정, 성장률, 초기투자비", 3)
    basic_rows = [
        ["사업명", assumptions.get("business_name", "")],
        ["업종", assumptions.get("industry", "")],
        ["분석기간", f"{assumptions.get('analysis_years', '')}년"],
        ["기준통화", assumptions.get("currency", "KRW")],
        ["세율", pct_point(assumptions.get("tax_rate_pct", 0))],
    ]
    growth_rows = [
        ["매출 성장률", pct_point(assumptions.get("revenue_growth_pct", 0))],
        ["비용 증가율", pct_point(assumptions.get("cost_growth_pct", 0))],
        ["인건비 증가율", pct_point(assumptions.get("labor_growth_pct", 0))],
        ["임대료 증가율", pct_point(assumptions.get("rent_growth_pct", 0))],
        ["기타 비용 증가율", pct_point(assumptions.get("other_growth_pct", 0))],
    ]
    invest_rows = [[key, money_m(value)] for key, value in initial.items()]
    invest_rows.append(["합계", money_m(sum(float(v) for v in initial.values()))])
    col_w = (PAGE_W - MARGIN * 2 - 32) / 3
    p.table(MARGIN, 478, col_w, "기본 설정", ["항목", "값"], basic_rows, [0.42, 0.58], row_h=30, size=9.8)
    p.table(MARGIN + col_w + 16, 478, col_w, "성장률", ["항목", "값"], growth_rows, [0.58, 0.42], row_h=30, size=9.8, right_cols={1})
    p.table(MARGIN + (col_w + 16) * 2, 478, col_w, "초기투자비", ["항목", "금액"], invest_rows, [0.58, 0.42], row_h=26, size=9.3, right_cols={1}, highlight_rows={len(invest_rows) - 1})
    pdf.showPage()

    # Page 4: Revenue & Cost Inputs
    p.page_header("Input Assumptions Summary 2", "매출 및 비용 입력 핵심 요약", 4)
    rev_rows = [
        [row["매출항목명"], row["계산방식"], money_m(row["단가"]), number_1(row["수량/이용자수"]), row["발생주기"], pct_point(row["연간성장률(%)"])]
        for _, row in revenue_df.iterrows()
    ]
    cost_rows = [
        [row["비용항목명"], row["비용유형"], money_m(row["월비용"]), money_m(row["연비용"]), pct_point(row["매출대비비율(%)"]), pct_point(row["연간증가율(%)"])]
        for _, row in cost_df.iterrows()
    ]
    p.table(MARGIN, 478, PAGE_W - MARGIN * 2, "매출 입력 핵심 요약", ["항목명", "계산방식", "단가", "수량/이용자", "주기", "성장률"], rev_rows, [0.25, 0.22, 0.15, 0.14, 0.10, 0.14], row_h=30, size=9.1, right_cols={2, 3, 5}, max_rows=4)
    p.table(MARGIN, 270, PAGE_W - MARGIN * 2, "비용 입력 핵심 요약", ["항목명", "유형", "월비용", "연비용", "매출대비", "증가율"], cost_rows, [0.28, 0.15, 0.15, 0.15, 0.13, 0.14], row_h=27, size=9.0, right_cols={2, 3, 4, 5}, max_rows=5)
    pdf.showPage()

    # Page 5: Staffing Inputs
    p.page_header("Input Assumptions Summary 3", "인력 입력 핵심 요약", 5)
    staff_rows = [
        [row["직무명"], number_1(row["인원수"]), money_m(row["1인당월급"]), pct_point(row["4대보험/복리후생비율(%)"]), pct_point(row["연봉상승률(%)"]), pct_point(row["연간인원증가율(%)"])]
        for _, row in staffing_df.iterrows()
    ]
    p.table(MARGIN, 478, PAGE_W - MARGIN * 2, "인력 입력 핵심 요약", ["직무명", "인원", "1인당 월급", "복리후생", "연봉상승", "인원증가"], staff_rows, [0.28, 0.12, 0.18, 0.15, 0.14, 0.13], row_h=32, size=9.4, right_cols={1, 2, 3, 4, 5}, max_rows=8)
    p.card(MARGIN, 92, PAGE_W - MARGIN * 2, 92)
    p.text("Note", MARGIN + 18, 152, 12, "PretendardPDF", "ink")
    p.wrapped("인력계획을 비용에 자동 반영하는 경우 인건비는 비용 모델에 포함됩니다. 본 표는 입력 가정 확인용이며, 금액은 모두 백만원 단위로 표시했습니다.", MARGIN + 18, 128, PAGE_W - MARGIN * 2 - 36, 10.4, "PretendardPDF", "ink", max_lines=3)
    pdf.showPage()

    # Page 6: Dashboard
    p.page_header("Dashboard View", "핵심 숫자, 주요 추세, 의사결정 포인트", 6)
    dashboard_cards = [
        ("총매출", money_m(kpis["총매출"]), "누적", "red"),
        ("영업이익", money_m(kpis["영업이익"]), "누적", "orange"),
        ("순이익", money_m(kpis["순이익"]), "누적", "red"),
        ("영업이익률", pct_ratio(kpis["영업이익률"]), "수익성", "orange"),
        ("투자회수", str(kpis["투자회수기간"]), "Payback", "red"),
        ("손익분기매출", money_m(kpis["손익분기매출(1년차)"]), "Year 1", "orange"),
    ]
    for idx, item in enumerate(dashboard_cards):
        p.kpi_card(MARGIN + (idx % 3) * 256, 426 - (idx // 3) * 72, 234, 56, *item)
    p.line_chart(MARGIN, 150, 360, 170, "연도별 매출 추이", {"총매출": model_result["series"]["revenue"]})
    p.bar_chart(438, 150, 360, 170, "영업이익 및 순이익 추이", {"영업이익": model_result["series"]["operating_income"], "순이익": model_result["series"]["net_income"]})
    p.card(MARGIN, 66, PAGE_W - MARGIN * 2, 58)
    p.text("Decision Point", MARGIN + 18, 100, 12, "PretendardPDF", "ink")
    p.wrapped(f"누적 영업이익률 {pct_ratio(kpis['영업이익률'])}, ROI {pct_ratio(kpis['ROI'])}, 투자회수기간 {kpis['투자회수기간']} 기준으로 사업성을 판단합니다.", MARGIN + 130, 100, PAGE_W - MARGIN * 2 - 150, 10.2, "PretendardPDF", "ink", max_lines=2)
    pdf.showPage()

    # Page 7: P&L
    p.page_header("Profit & Loss Statement", "손익계산서: 연도별 추정치, 단위: 백만원", 7)
    pnl = model_result["pnl"].copy()
    years = [col for col in pnl.columns if str(col).startswith("Year")]
    key_rows = {"총매출", "매출총이익", "EBITDA", "영업이익", "순이익", "누적 순이익", "영업이익률", "순이익률"}
    pnl_rows: list[list[str]] = []
    highlight_rows: set[int] = set()
    for _, row in pnl.iterrows():
        item = row["항목"]
        values = [pct_ratio(row[year]) if "률" in item else money_m(row[year], "") for year in years]
        if item in key_rows:
            highlight_rows.add(len(pnl_rows))
        pnl_rows.append([item, *values])
    p.table(MARGIN, 478, PAGE_W - MARGIN * 2, "손익계산서 (금액 단위: 백만원, 비율: %)", ["항목", *years], pnl_rows, [0.25, 0.15, 0.15, 0.15, 0.15, 0.15], row_h=22, size=8.9, right_cols={1, 2, 3, 4, 5}, highlight_rows=highlight_rows)
    pdf.showPage()

    # Page 8: Cash Flow
    p.page_header("Cash Flow & Payback Analysis", "Year 0부터 누적현금흐름 전환 시점까지", 8)
    cash_rows: list[list[str]] = []
    highlight: set[int] = set()
    for idx, row in model_result["cash_flow"].iterrows():
        cash_rows.append([row["연도"], money_m(row["현금흐름"]), money_m(row["누적현금흐름"])])
        if str(row["연도"]) == "Year 0" or (float(row["누적현금흐름"]) >= 0 and idx > 0):
            highlight.add(len(cash_rows) - 1)
    p.table(MARGIN, 456, 330, "현금흐름표", ["연도", "현금흐름", "누적현금흐름"], cash_rows, [0.28, 0.36, 0.36], row_h=32, size=9.6, right_cols={1, 2}, highlight_rows=highlight)
    p.line_chart(400, 204, 398, 252, "누적현금흐름 추이", {"누적현금흐름": model_result["series"]["cumulative_cash_flow"]})
    p.card(400, 92, 398, 82)
    p.text("Payback Insight", 418, 144, 13, "PretendardPDF", "ink")
    p.wrapped(f"투자회수기간은 {kpis['투자회수기간']}이며, Year 0의 초기투자비는 음수 현금흐름으로 반영됩니다.", 418, 120, 356, 10.5, "PretendardPDF", "ink", max_lines=2)
    pdf.showPage()

    # Page 9: Break-even
    p.page_header("Break-even Analysis", "손익분기매출과 예상매출 비교", 9)
    break_rows: list[list[str]] = []
    for _, row in model_result["break_even"].iterrows():
        year = row["연도"]
        expected = float(model_result["series"]["revenue"].get(year, 0))
        be_sales = float(row["손익분기매출"])
        excess = expected - be_sales
        safety = excess / expected * 100 if expected else 0
        break_rows.append([year, money_m(expected), money_m(be_sales), money_m(excess), pct_point(safety), pct_ratio(row["공헌이익률"]), number_1(row["손익분기판매량"])])
    p.table(MARGIN, 478, PAGE_W - MARGIN * 2, "손익분기점 비교표", ["연도", "예상매출", "손익분기매출", "초과매출", "안전마진율", "공헌이익률", "손익분기판매량"], break_rows, [0.10, 0.15, 0.17, 0.15, 0.14, 0.14, 0.15], row_h=25, size=8.8, right_cols={1, 2, 3, 4, 5, 6})
    break_even_series = pd.Series({row["연도"]: row["손익분기매출"] for _, row in model_result["break_even"].iterrows()}, name="손익분기 매출")
    p.line_chart(MARGIN, 86, 360, 188, "예상매출 vs 손익분기매출", {"예상 매출": model_result["series"]["revenue"], "손익분기 매출": break_even_series})
    p.card(438, 86, 360, 188)
    p.text("Decision Point", 458, 230, 13, "PretendardPDF", "ink")
    p.wrapped("예상매출이 손익분기매출을 안정적으로 초과하면 고정비 부담을 흡수할 여지가 커집니다. 안전마진율이 낮은 연도는 가격, 판매량, 비용 구조 조정이 필요한 구간입니다.", 458, 202, 318, 10.2, "PretendardPDF", "ink", max_lines=6)
    pdf.showPage()

    pdf.save()
    return output.getvalue()
