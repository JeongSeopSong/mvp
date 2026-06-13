"""Vector/text based PDF report generator for the Streamlit MVP."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


BASE_DIR = Path(__file__).resolve().parent
FONT_DIR = BASE_DIR / "assets" / "fonts"


PAGE_W = 960
PAGE_H = 540
MARGIN = 44


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
    fonts = {
        "Pretendard": FONT_DIR / "PretendardStd-Regular.ttf",
        "PretendardSemi": FONT_DIR / "PretendardStd-SemiBold.ttf",
        "PretendardBold": FONT_DIR / "PretendardStd-Bold.ttf",
    }
    for font_name, font_path in fonts.items():
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))


def money_m(value: Any, suffix: str = "백만원") -> str:
    try:
        number = float(value) / 1_000_000
    except (TypeError, ValueError):
        number = 0.0
    return f"{number:,.1f}{suffix}"


def number_1(value: Any) -> str:
    try:
        return f"{float(value):,.1f}"
    except (TypeError, ValueError):
        return str(value)


def pct(value: Any) -> str:
    try:
        return f"{float(value):,.1f}%"
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
        font: str = "Pretendard",
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
        font: str = "Pretendard",
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
        self.text("Business Profitability Assessment", MARGIN, 14, 8.8, "Pretendard", "muted")
        self.text(str(page_no), PAGE_W - MARGIN, 14, 8.8, "PretendardSemi", "muted", align="right")

    def page_header(self, title: str, subtitle: str, page_no: int) -> None:
        self.fill(PALETTE["bg"])
        self.pdf.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        self.text(title, MARGIN, PAGE_H - 56, 22, "PretendardBold", "ink")
        if subtitle:
            self.text(subtitle, MARGIN, PAGE_H - 78, 10.8, "Pretendard", "muted")
        self.fill(PALETTE["red"])
        self.pdf.rect(MARGIN, PAGE_H - 88, 56, 3, fill=1, stroke=0)
        self.fill(PALETTE["orange"])
        self.pdf.rect(MARGIN + 58, PAGE_H - 88, 36, 3, fill=1, stroke=0)
        self.footer(page_no)

    def kpi_card(self, x: float, y: float, w: float, h: float, label: str, value: str, note: str, accent: str = "red") -> None:
        self.card(x, y, w, h)
        self.fill(PALETTE[accent])
        self.pdf.roundRect(x, y, 5, h, 3, fill=1, stroke=0)
        self.text(label, x + 16, y + h - 21, 9.4, "PretendardSemi", "muted")
        self.text(value, x + 16, y + h - 48, 18.6, "PretendardBold", "ink")
        self.wrapped(note, x + 16, y + 17, w - 28, 8.4, "Pretendard", "muted", max_lines=1)

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
        self.text(title, x + 12, y_top - 20, 10.6, "PretendardSemi", "ink")
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
            self.text(head, lefts[idx] + 8, header_y + 9, 8.9, "PretendardSemi", "ink")
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
                font = "PretendardSemi" if row_idx in highlight_rows else "Pretendard"
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
            self.text(f"외 {len(rows) - max_rows}개 항목", x + w - 12, y + 8, 8.2, "Pretendard", "muted", align="right")
        return y

    def chart_frame(self, x: float, y: float, w: float, h: float, title: str, unit: str = "단위: 백만원") -> tuple[float, float, float, float]:
        self.card(x, y, w, h)
        self.text(title, x + 14, y + h - 22, 10.8, "PretendardSemi", "ink")
        self.text(unit, x + w - 14, y + h - 21, 8.8, "Pretendard", "muted", align="right")
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
            self.text(f"{label:,.0f}", px - 7, gy - 3, 8.3, "Pretendard", "muted", align="right")
        for i, label in enumerate(labels):
            tx = px + pw * i / max(len(labels) - 1, 1)
            self.text(label, tx, py - 18, 8.5, "Pretendard", "muted", align="center")
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
                self.text(f"{value:,.0f}", tx, ty + 8, 7.6, "PretendardSemi", "ink", align="center")
            lx = x + 14 + series_idx * 92
            self.fill(color)
            self.pdf.rect(lx, y + h - 41, 8, 8, fill=1, stroke=0)
            self.text(name, lx + 12, y + h - 40, 8.8, "Pretendard", "muted")

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
            self.text(label, px + group_w * i + group_w / 2, py - 18, 8.5, "Pretendard", "muted", align="center")
        for s_idx, (name, series) in enumerate(series_dict.items()):
            color = CHART_COLORS[s_idx % len(CHART_COLORS)]
            self.fill(color)
            for i, raw in enumerate(series.tolist()):
                value = float(raw) / 1_000_000
                cx = px + group_w * i + group_w / 2
                bx = cx - (series_count * bar_w) / 2 + s_idx * bar_w
                by = py + ((value - y_min) / (y_max - y_min)) * ph
                self.pdf.rect(bx, min(zero_y, by), bar_w * 0.78, abs(by - zero_y), fill=1, stroke=0)
                self.text(f"{value:,.0f}", bx + bar_w * 0.39, max(zero_y, by) + 6, 7.5, "PretendardSemi", "ink", align="center")
            lx = x + 14 + s_idx * 92
            self.pdf.rect(lx, y + h - 41, 8, 8, fill=1, stroke=0)
            self.text(name, lx + 12, y + h - 40, 8.8, "Pretendard", "muted")


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
    pdf.rect(0, 0, 330, PAGE_H, fill=1, stroke=0)
    p.fill(PALETTE["red"])
    pdf.rect(0, PAGE_H - 128, 330, 128, fill=1, stroke=0)
    p.fill(PALETTE["orange"])
    pdf.rect(330, PAGE_H - 128, 72, 128, fill=1, stroke=0)
    p.text("Business", 54, 322, 30, "PretendardBold", "paper")
    p.text("Profitability", 54, 284, 30, "PretendardBold", "paper")
    p.text("Report", 54, 246, 30, "PretendardBold", "paper")
    p.text("사업 수익성 분석 보고서", 400, 342, 33, "PretendardBold", "ink")
    p.wrapped("현재 입력값과 결과 대시보드를 바탕으로 작성된 투자검토용 요약 보고서입니다.", 404, 306, 460, 13, "Pretendard", "muted", max_lines=2)
    meta = [
        ["사업명", assumptions.get("business_name", "")],
        ["업종", assumptions.get("industry", "")],
        ["분석기간", f"{assumptions.get('analysis_years', '')}년"],
        ["기준 통화", assumptions.get("currency", "KRW")],
    ]
    p.table(404, 252, 430, "Report Scope", ["구분", "내용"], meta, [0.28, 0.72], row_h=28, size=10.2)
    p.text("Prepared for decision review", 404, 76, 10.5, "Pretendard", "muted")
    p.footer(1)
    pdf.showPage()

    # Page 2: Executive Summary
    p.page_header("Executive Summary & Key KPI", "핵심 숫자와 의사결정 포인트", 2)
    kpi_items = [
        ("총매출", money_m(kpis["총매출"]), "분석기간 누적 매출", "red"),
        ("영업이익", money_m(kpis["영업이익"]), "총비용 차감 후 영업성과", "orange"),
        ("순이익", money_m(kpis["순이익"]), "세금 반영 후 최종 이익", "red"),
        ("영업이익률", pct(kpis["영업이익률"]), "누적 매출 대비", "orange"),
        ("투자회수기간", str(kpis["투자회수기간"]), "누적현금흐름 기준", "red"),
        ("ROI", pct(kpis["ROI"]), "5년 누적 순이익 / 초기투자비", "orange"),
    ]
    for idx, item in enumerate(kpi_items):
        p.kpi_card(MARGIN + (idx % 3) * 294, 342 - (idx // 3) * 88, 270, 70, *item)
    p.card(MARGIN, 86, PAGE_W - MARGIN * 2, 165)
    p.text("Decision Readout", MARGIN + 18, 220, 14, "PretendardBold", "ink")
    bullets = [
        f"영업이익률은 {pct(kpis['영업이익률'])}로 추정됩니다.",
        f"ROI는 {pct(kpis['ROI'])}이며, 초기투자비 대비 5년 누적 순이익 기준입니다.",
        f"투자회수기간은 {kpis['투자회수기간']}입니다.",
        f"1년차 손익분기매출은 {money_m(kpis['손익분기매출(1년차)'])}입니다.",
    ]
    for idx, bullet in enumerate(bullets):
        p.fill(PALETTE["red"])
        pdf.circle(MARGIN + 23, 188 - idx * 28, 2.4, fill=1, stroke=0)
        p.wrapped(bullet, MARGIN + 34, 184 - idx * 28, PAGE_W - MARGIN * 2 - 64, 11.2, "Pretendard", "ink", max_lines=1)
    pdf.showPage()

    # Page 3: Input Summary 1
    p.page_header("Input Assumptions Summary 1", "기본설정, 성장률, 초기투자비", 3)
    basic_rows = [
        ["사업명", assumptions.get("business_name", "")],
        ["업종", assumptions.get("industry", "")],
        ["분석기간", f"{assumptions.get('analysis_years', '')}년"],
        ["기준통화", assumptions.get("currency", "KRW")],
        ["세율", pct(assumptions.get("tax_rate_pct", 0))],
    ]
    growth_rows = [
        ["매출 성장률", pct(assumptions.get("revenue_growth_pct", 0))],
        ["비용 증가율", pct(assumptions.get("cost_growth_pct", 0))],
        ["인건비 증가율", pct(assumptions.get("labor_growth_pct", 0))],
        ["임대료 증가율", pct(assumptions.get("rent_growth_pct", 0))],
        ["기타 비용 증가율", pct(assumptions.get("other_growth_pct", 0))],
    ]
    invest_rows = [[key, money_m(value)] for key, value in initial.items()]
    invest_rows.append(["합계", money_m(sum(float(v) for v in initial.values()))])
    p.table(MARGIN, 438, 278, "기본 설정", ["항목", "값"], basic_rows, [0.42, 0.58], row_h=28, size=10)
    p.table(346, 438, 278, "성장률", ["항목", "값"], growth_rows, [0.58, 0.42], row_h=28, size=10, right_cols={1})
    p.table(648, 438, 268, "초기투자비", ["항목", "금액"], invest_rows, [0.58, 0.42], row_h=25, size=9.5, right_cols={1}, highlight_rows={len(invest_rows) - 1})
    pdf.showPage()

    # Page 4: Input Summary 2
    p.page_header("Input Assumptions Summary 2", "매출, 비용, 인력 입력 핵심 요약", 4)
    rev_rows = [
        [row["매출항목명"], row["계산방식"], money_m(row["단가"]), number_1(row["수량/이용자수"]), row["발생주기"], pct(row["연간성장률(%)"])]
        for _, row in revenue_df.iterrows()
    ]
    cost_rows = [
        [row["비용항목명"], row["비용유형"], money_m(row["월비용"]), money_m(row["연비용"]), pct(row["매출대비비율(%)"]), pct(row["연간증가율(%)"])]
        for _, row in cost_df.iterrows()
    ]
    staff_rows = [
        [row["직무명"], number_1(row["인원수"]), money_m(row["1인당월급"]), pct(row["4대보험/복리후생비율(%)"]), pct(row["연봉상승률(%)"]), pct(row["연간인원증가율(%)"])]
        for _, row in staffing_df.iterrows()
    ]
    p.table(MARGIN, 440, PAGE_W - MARGIN * 2, "매출 입력 핵심 요약", ["항목명", "계산방식", "단가", "수량/이용자", "주기", "성장률"], rev_rows, [0.25, 0.22, 0.15, 0.14, 0.10, 0.14], row_h=28, size=9.4, right_cols={2, 3, 5}, max_rows=4)
    p.table(MARGIN, 278, PAGE_W - MARGIN * 2, "비용 입력 핵심 요약", ["항목명", "유형", "월비용", "연비용", "매출대비", "증가율"], cost_rows, [0.28, 0.15, 0.15, 0.15, 0.13, 0.14], row_h=24, size=9.2, right_cols={2, 3, 4, 5}, max_rows=5)
    p.table(MARGIN, 134, PAGE_W - MARGIN * 2, "인력 입력 핵심 요약", ["직무명", "인원", "월급", "복리후생", "연봉상승", "인원증가"], staff_rows, [0.28, 0.12, 0.17, 0.15, 0.14, 0.14], row_h=25, size=9.2, right_cols={1, 2, 3, 4, 5}, max_rows=3)
    pdf.showPage()

    # Page 5: Dashboard
    p.page_header("Dashboard View", "핵심 숫자, 추세, 의사결정 포인트", 5)
    dashboard_cards = [
        ("총매출", money_m(kpis["총매출"]), "누적", "red"),
        ("영업이익", money_m(kpis["영업이익"]), "누적", "orange"),
        ("순이익", money_m(kpis["순이익"]), "누적", "red"),
        ("영업이익률", pct(kpis["영업이익률"]), "수익성", "orange"),
        ("투자회수", str(kpis["투자회수기간"]), "Payback", "red"),
        ("손익분기매출", money_m(kpis["손익분기매출(1년차)"]), "Year 1", "orange"),
    ]
    for idx, item in enumerate(dashboard_cards):
        p.kpi_card(MARGIN + idx * 145, 398, 128, 58, *item)
    p.line_chart(MARGIN, 236, 412, 135, "연도별 매출 추이", {"총매출": model_result["series"]["revenue"]})
    p.line_chart(504, 236, 412, 135, "연도별 비용 추이", {"총비용": model_result["series"]["total_cost"]})
    p.bar_chart(MARGIN, 76, 412, 135, "영업이익 및 순이익 추이", {"영업이익": model_result["series"]["operating_income"], "순이익": model_result["series"]["net_income"]})
    p.line_chart(504, 76, 412, 135, "누적 현금흐름", {"누적현금흐름": model_result["series"]["cumulative_cash_flow"]})
    pdf.showPage()

    # Page 6: P&L
    p.page_header("Profit & Loss Statement", "손익계산서: 연도별 추정치, 단위: 백만원", 6)
    pnl = model_result["pnl"].copy()
    years = [col for col in pnl.columns if str(col).startswith("Year")]
    key_rows = {"총매출", "매출총이익", "EBITDA", "영업이익", "순이익", "누적 순이익", "영업이익률", "순이익률"}
    pnl_rows: list[list[str]] = []
    highlight_rows: set[int] = set()
    for _, row in pnl.iterrows():
        item = row["항목"]
        values = [pct(row[year]) if "률" in item else money_m(row[year], "") for year in years]
        if item in key_rows:
            highlight_rows.add(len(pnl_rows))
        pnl_rows.append([item, *values])
    p.table(MARGIN, 438, PAGE_W - MARGIN * 2, "손익계산서 (금액 단위: 백만원, 비율: %)", ["항목", *years], pnl_rows, [0.25, 0.15, 0.15, 0.15, 0.15, 0.15], row_h=22, size=9.2, right_cols={1, 2, 3, 4, 5}, highlight_rows=highlight_rows)
    pdf.showPage()

    # Page 7: Cash Flow
    p.page_header("Cash Flow & Payback Analysis", "Year 0부터 누적현금흐름 전환 시점까지", 7)
    cash_rows: list[list[str]] = []
    highlight: set[int] = set()
    for idx, row in model_result["cash_flow"].iterrows():
        cash_rows.append([row["연도"], money_m(row["현금흐름"]), money_m(row["누적현금흐름"])])
        if str(row["연도"]) == "Year 0" or (float(row["누적현금흐름"]) >= 0 and idx > 0):
            highlight.add(len(cash_rows) - 1)
    p.table(MARGIN, 420, 360, "현금흐름표", ["연도", "현금흐름", "누적현금흐름"], cash_rows, [0.28, 0.36, 0.36], row_h=34, size=10, right_cols={1, 2}, highlight_rows=highlight)
    p.line_chart(444, 190, 472, 230, "누적현금흐름 추이", {"누적현금흐름": model_result["series"]["cumulative_cash_flow"]})
    p.card(444, 86, 472, 78)
    p.text("Payback Insight", 462, 137, 13, "PretendardBold", "ink")
    p.wrapped(f"투자회수기간은 {kpis['투자회수기간']}이며, Year 0의 초기투자비는 음수 현금흐름으로 반영됩니다.", 462, 114, 430, 10.8, "Pretendard", "ink", max_lines=2)
    pdf.showPage()

    # Page 8: Break-even
    p.page_header("Break-even Analysis", "손익분기매출과 예상매출 비교", 8)
    break_rows: list[list[str]] = []
    for _, row in model_result["break_even"].iterrows():
        year = row["연도"]
        expected = float(model_result["series"]["revenue"].get(year, 0))
        be_sales = float(row["손익분기매출"])
        excess = expected - be_sales
        safety = excess / expected * 100 if expected else 0
        break_rows.append([year, money_m(expected), money_m(be_sales), money_m(excess), pct(safety), pct(row["공헌이익률"]), number_1(row["손익분기판매량"])])
    p.table(MARGIN, 426, PAGE_W - MARGIN * 2, "손익분기점 비교표", ["연도", "예상매출", "손익분기매출", "초과매출", "안전마진율", "공헌이익률", "손익분기판매량"], break_rows, [0.10, 0.15, 0.17, 0.15, 0.14, 0.14, 0.15], row_h=26, size=9.3, right_cols={1, 2, 3, 4, 5, 6})
    break_even_series = pd.Series({row["연도"]: row["손익분기매출"] for _, row in model_result["break_even"].iterrows()}, name="손익분기 매출")
    p.line_chart(MARGIN, 82, 412, 185, "예상매출 vs 손익분기매출", {"예상 매출": model_result["series"]["revenue"], "손익분기 매출": break_even_series})
    p.card(504, 82, 412, 185)
    p.text("Decision Point", 526, 224, 14, "PretendardBold", "ink")
    p.wrapped("예상매출이 손익분기매출을 안정적으로 초과하면 고정비 부담을 흡수할 여지가 커집니다. 안전마진율이 낮은 연도는 가격, 판매량, 비용 구조 조정이 필요한 구간입니다.", 526, 194, 366, 11, "Pretendard", "ink", max_lines=5)
    pdf.showPage()

    pdf.save()
    return output.getvalue()
