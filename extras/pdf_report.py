
"""Tạo báo cáo PDF chẩn đoán mạng cho NetGuard."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Rect, String, Line
from models import now

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# =========================================================
# 1. FONT TIẾNG VIỆT
# =========================================================

FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "NotoSans-Regular.ttf"


def register_font():
    if "ArialVN" in pdfmetrics.getRegisteredFontNames():
        return
    candidates = [FONT_PATH, Path("C:/Windows/Fonts/arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
    for candidate in candidates:
        if candidate.is_file():
            pdfmetrics.registerFont(TTFont("ArialVN", str(candidate)))
            return
    raise RuntimeError("Thiếu font PDF. Khôi phục assets/fonts/NotoSans-Regular.ttf từ mã nguồn.")


# =========================================================
# 2. HÀM HỖ TRỢ
# =========================================================

def format_time(value) -> str:
    """Chuyển thời gian thành chuỗi dễ đọc."""

    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M:%S")

    return str(value) if value is not None else "-"


def format_number(value, digits=2) -> str:
    """Định dạng số, tránh lỗi khi giá trị là None."""

    if value is None:
        return "-"

    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def get_value(obj, key, default=None):
    """Đọc thuộc tính từ dict hoặc dataclass."""

    if isinstance(obj, dict):
        return obj.get(key, default)

    return getattr(obj, key, default)


def safe_text(value) -> str:
    """Chuyển dữ liệu thành chuỗi an toàn cho Paragraph."""

    if value is None:
        return "-"

    return escape(str(value))


def create_table(rows, widths=None):
    """Tạo bảng PDF với font tiếng Việt."""

    table = Table(
        rows,
        colWidths=widths,
        repeatRows=1,
        hAlign="LEFT",
    )

    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "ArialVN"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 11),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCEAF7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#16324F")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    return table


def draw_page_number(canvas, doc):
    """Đánh số trang ở cuối PDF."""

    canvas.saveState()
    canvas.setFont("ArialVN", 8)
    canvas.setFillColor(colors.grey)

    canvas.drawRightString(
        A4[0] - 36,
        22,
        f"NetGuard - Trang {doc.page}"
    )

    canvas.restoreState()


# =========================================================
# 3. TẠO BIỂU ĐỒ
# =========================================================

def create_ping_chart(ping_stats: dict):
    """Biểu đồ vector; thiếu dữ liệu hiện N/A, không vẽ giá trị 0 giả."""
    drawing = Drawing(510, 250)
    for metric, title, base_y, color in (("rtt_median_ms", "RTT trung vị (ms)", 150, "#2878B5"),
                                         ("loss_pct", "Mất gói của probe đã gửi (%)", 25, "#E58B36")):
        values = [ping_stats.get(t, {}).get(metric) for t in ("router", "isp", "external")]
        maximum = max([float(v) for v in values if v is not None]+[1 if metric == "rtt_median_ms" else 100])
        drawing.add(String(20, base_y+92, title, fontName="ArialVN", fontSize=10))
        drawing.add(Line(20, base_y, 495, base_y, strokeColor=colors.lightgrey))
        for index, (label, value) in enumerate(zip(("Router", "Hop sau gateway", "Đích ngoài"), values)):
            x = 45+index*160
            if value is not None:
                height = float(value)/maximum*65
                drawing.add(Rect(x, base_y, 65, height, fillColor=colors.HexColor(color), strokeColor=None))
                text = f"{value:.1f}"
            else:
                height, text = 0, "N/A"
            drawing.add(String(x+32, base_y+height+5, text, textAnchor="middle", fontName="ArialVN", fontSize=9))
            drawing.add(String(x+32, base_y-15, label, textAnchor="middle", fontName="ArialVN", fontSize=9))
    return drawing


# =========================================================
# 4. TẠO BÁO CÁO PDF
# =========================================================

def build_report(data: dict, path: str, stop_event=None) -> None:
    """Tạo báo cáo PDF từ dữ liệu Backend.export_report."""

    register_font()
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "NetGuardTitle",
        parent=styles["Title"],
        fontName="ArialVN",
        fontSize=17,
        leading=23,
        alignment=TA_CENTER,
        spaceAfter=15,
    )

    heading_style = ParagraphStyle(
        "NetGuardHeading",
        parent=styles["Heading2"],
        fontName="ArialVN",
        fontSize=12,
        leading=17,
        textColor=colors.HexColor("#174A75"),
        spaceBefore=14,
        spaceAfter=8,
    )

    normal_style = ParagraphStyle(
        "NetGuardNormal",
        parent=styles["Normal"],
        fontName="ArialVN",
        fontSize=9,
        leading=14,
        spaceAfter=5,
        wordWrap="CJK",
    )

    def paragraph(value):
        return Paragraph(safe_text(value), normal_style)

    story = []


    # -----------------------------------------------------
    # TIÊU ĐỀ
    # -----------------------------------------------------

    story.append(Paragraph(
        "BÁO CÁO CHẨN ĐOÁN MẠNG NETGUARD",
        title_style,
    ))

    story.append(paragraph(
        "Báo cáo tổng hợp tình trạng kết nối mạng, "
        "phục vụ theo dõi và cung cấp bằng chứng "
        "khi liên hệ nhà cung cấp Internet."
    ))

    story.append(Spacer(1, 10))

    # -----------------------------------------------------
    # 1. THÔNG TIN GIÁM SÁT
    # -----------------------------------------------------

    story.append(Paragraph(
        "1. THÔNG TIN GIÁM SÁT",
        heading_style,
    ))

    story.append(paragraph(
        f"Thời gian bắt đầu: {format_time(data.get('start'))}"
    ))

    story.append(paragraph(
        f"Thời gian kết thúc: {format_time(data.get('end'))}"
    ))

    interface = data.get("interface", {}) or {}

    if isinstance(interface, dict) and interface:
        interface_rows = [
            ["Thông số", "Giá trị"]
        ]

        for key, value in interface.items():
            interface_rows.append([
                paragraph(key),
                paragraph(value),
            ])

        story.append(create_table(
            interface_rows,
            [150, 370],
        ))
    else:
        story.append(paragraph(
            "Chưa có thông tin giao diện mạng."
        ))

    for text in data.get("coverage_notes", []):
        story.append(paragraph(text))
    for session in data.get("sessions", [])[:100]:
        interface_at_measurement = session.get("interface", {})
        story.append(paragraph(f"Phiên {session['id'][:8]}: {format_time(session['started'])} - {format_time(session.get('ended') or data.get('end'))}; card {interface_at_measurement.get('name', '?')}, IPv4 {interface_at_measurement.get('ip', '?')}, gateway {interface_at_measurement.get('gateway', '?')}"))

    # -----------------------------------------------------
    # 2. THỐNG KÊ PING
    # -----------------------------------------------------

    story.append(Paragraph(
        "2. THỐNG KÊ KẾT QUẢ PING",
        heading_style,
    ))

    ping_stats = data.get("ping_stats", {}) or {}

    table_data = [[
        "Mốc",
        "Số mẫu",
        "Mất gói (%)",
        "RTT min",
        "RTT median",
        "RTT max",
    ]]

    for target in ("router", "isp", "external"):
        stats = ping_stats.get(target, {}) or {}

        table_data.append([
            target,
            str(stats.get("samples", 0)),
            format_number(stats.get("loss_pct")),
            format_number(stats.get("rtt_min_ms")),
            format_number(stats.get("rtt_median_ms")),
            format_number(stats.get("rtt_max_ms")),
        ])

    story.append(create_table(
        table_data,
        [75, 65, 95, 90, 100, 95],
    ))

    story.append(Spacer(1, 8))

    story.append(paragraph(
        "Đơn vị RTT: mili giây (ms). "
        "Giá trị '-' nghĩa là chưa có dữ liệu phản hồi."
    ))

    # -----------------------------------------------------
    # 3. BIỂU ĐỒ
    # -----------------------------------------------------

    story.append(Paragraph(
        "3. BIỂU ĐỒ RTT VÀ TỶ LỆ MẤT GÓI",
        heading_style,
    ))

    if ping_stats:
        story.append(create_ping_chart(ping_stats))
    else:
        story.append(paragraph(
            "Không có dữ liệu để vẽ biểu đồ."
        ))

    # -----------------------------------------------------
    # 4. LỊCH SỬ MẤT GÓI
    # -----------------------------------------------------

    story.append(Paragraph(
        "4. LỊCH SỬ MẤT GÓI",
        heading_style,
    ))

    loss_events = data.get("loss_events", []) or []

    if loss_events:
        loss_rows = [[
            "STT",
            "Mốc kiểm tra",
            "Thời điểm mất gói",
        ]]

        for index, event in enumerate(loss_events[:500], start=1):
            loss_rows.append([
                str(index),
                str(get_value(event, "target", "-")) + f" ({get_value(event, 'count', 1)} probe)",
                format_time(get_value(event, "ts")),
            ])

        story.append(create_table(
            loss_rows,
            [50, 150, 320],
        ))
    else:
        story.append(paragraph(
            "Không có probe timeout được lưu trong khoảng này; cần xem số mẫu và độ phủ giám sát, không suy ra mất gói 0% nếu thiếu dữ liệu."
        ))

    # -----------------------------------------------------
    # 5. KẾT LUẬN CHẨN ĐOÁN
    # -----------------------------------------------------

    story.append(Paragraph(
        "5. KẾT LUẬN CHẨN ĐOÁN MẠNG",
        heading_style,
    ))

    diagnoses = data.get("diagnoses", []) or []

    verdict_names = {
        "ok": "Mạng bình thường",
        "home_issue": "Lỗi mạng nội bộ",
        "isp_issue": "Lỗi đường truyền ISP",
        "internet_issue": "Lỗi Internet hoặc máy chủ đích",
        "unknown": "Chưa đủ dữ liệu",
    }

    if diagnoses:
        for index, item in enumerate(diagnoses, start=1):
            verdict = get_value(item, "verdict", "unknown")
            message = get_value(item, "text", "")
            ts = get_value(item, "ts")

            story.append(KeepTogether([
                paragraph(
                    f"{index}. {format_time(ts)} - "
                    f"{verdict_names.get(verdict, verdict)}"
                ),
                paragraph(message),
                Spacer(1, 5),
            ]))
    else:
        story.append(paragraph(
            "Chưa ghi nhận kết luận chẩn đoán trong khoảng thời gian này."
        ))

    # -----------------------------------------------------
    # 6. TRACEROUTE
    # -----------------------------------------------------

    story.append(Paragraph(
        "6. KẾT QUẢ TRACEROUTE",
        heading_style,
    ))

    traceroute = data.get("traceroute", []) or []

    if traceroute:
        for trace in traceroute:
            trace_time = get_value(trace, "ts")
            hops = get_value(trace, "hops", []) or []

            story.append(paragraph(
                f"Thời điểm traceroute: {format_time(trace_time)}"
            ))

            if not hops:
                story.append(paragraph(
                    "Không có thông tin các chặng."
                ))
                continue

            hop_rows = [[
                "TTL",
                "Địa chỉ IP",
                "RTT (ms)",
                "Đánh dấu",
            ]]

            for hop in hops:
                hop_rows.append([
                    str(get_value(hop, "ttl", "-")),
                    str(get_value(hop, "ip") or "*"),
                    format_number(get_value(hop, "rtt_ms")),
                    "Có" if get_value(hop, "flagged", False) else "Không",
                ])

            story.append(create_table(
                hop_rows,
                [65, 200, 120, 135],
            ))

            story.append(Spacer(1, 10))
    else:
        story.append(paragraph(
            "Chưa có dữ liệu traceroute trong khoảng thời gian báo cáo."
        ))

    # -----------------------------------------------------
    # 7. GHI CHÚ
    # -----------------------------------------------------

    story.append(Paragraph(
        "7. GHI CHÚ",
        heading_style,
    ))

    story.append(paragraph(
        "Báo cáo được tạo tự động từ dữ liệu NetGuard. "
        "Các kết luận phản ánh kết quả đo tại thời điểm giám sát "
        "và không tự xác định chắc chắn nguyên nhân sự cố."
    ))

    story.append(Spacer(1, 12))

    story.append(paragraph(
        f"Thời điểm tạo báo cáo: "
        f"{format_time(now())} (GMT+7)"
    ))

    # -----------------------------------------------------
    # XUẤT FILE PDF
    # -----------------------------------------------------

    def page(canvas, doc):
        if stop_event is not None and stop_event.is_set():
            raise RuntimeError("Đã hủy xuất báo cáo.")
        draw_page_number(canvas, doc)
    doc.build(story, onFirstPage=page, onLaterPages=page)
