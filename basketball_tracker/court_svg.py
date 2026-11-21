"""Self-contained dark-themed inline SVG half-court visualization."""

from collections.abc import Mapping
from html import escape

from basketball_tracker.models import ShotTotals, format_percentage


def _zone_badge(
    *,
    zone_id: str,
    center_x: int,
    center_y: int,
    title: str,
    shots: ShotTotals,
    accent: str,
) -> str:
    width = 148
    height = 54
    x = center_x - width // 2
    y = center_y - height // 2
    pct_text = escape(format_percentage(shots.percentage))
    ratio_text = escape(f"{shots.makes} / {shots.attempts}")
    label_text = escape(title)
    pct_color = "#F8FAFC" if shots.attempts > 0 else "#94A3B8"
    return (
        f'<g data-zone="{escape(zone_id)}">\n'
        f'  <rect x="{x}" y="{y}" width="{width}" height="{height}" rx="10" '
        f'fill="#0B1120" fill-opacity="0.94" stroke="#334155" stroke-width="1.5" />\n'
        f'  <rect x="{x + 12}" y="{y}" width="{width - 24}" height="3" rx="1.5" fill="{accent}" />\n'
        f'  <text x="{center_x}" y="{y + 16}" text-anchor="middle" fill="#94A3B8" '
        f'font-size="10" font-weight="700" letter-spacing="0.08em">{label_text}</text>\n'
        f'  <text x="{center_x}" y="{y + 35}" text-anchor="middle" fill="{pct_color}" '
        f'font-size="18" font-weight="800" style="font-variant-numeric: tabular-nums;">{pct_text}</text>\n'
        f'  <text x="{center_x}" y="{y + 48}" text-anchor="middle" fill="#CBD5E1" '
        f'font-size="10.5" font-weight="600" style="font-variant-numeric: tabular-nums;">{ratio_text}</text>\n'
        f"</g>"
    )


def render_court_svg(
    totals: Mapping[str, ShotTotals],
    *,
    scope_label: str,
    session_count: int,
    date_label: str = "All dates",
) -> str:
    """Render an offline dark-mode half-court SVG with FT, 2PT, and 3PT stat badges."""
    free_throws = totals.get("Free throws", ShotTotals())
    two_pointers = totals.get("Two-pointers", ShotTotals())
    three_pointers = totals.get("Three-pointers", ShotTotals())

    safe_scope = escape(scope_label)
    session_word = "session" if session_count == 1 else "sessions"
    safe_subtitle = escape(f"{date_label} • {session_count} {session_word}")
    empty_banner = ""
    if session_count == 0:
        empty_banner = (
            '<g data-empty="true">\n'
            '  <rect x="176" y="106" width="208" height="24" rx="12" '
            'fill="#1E293B" stroke="#334155" stroke-width="1" />\n'
            '  <text x="280" y="122" text-anchor="middle" fill="#CBD5E1" '
            'font-size="11" font-weight="600">No sessions recorded</text>\n'
            "</g>\n"
        )

    ft_badge = _zone_badge(
        zone_id="free-throws",
        center_x=280,
        center_y=196,
        title="FREE THROWS",
        shots=free_throws,
        accent="#38BDF8",
    )
    two_badge = _zone_badge(
        zone_id="two-pointers",
        center_x=280,
        center_y=268,
        title="TWO-POINTERS",
        shots=two_pointers,
        accent="#34D399",
    )
    three_badge = _zone_badge(
        zone_id="three-pointers",
        center_x=280,
        center_y=352,
        title="THREE-POINTERS",
        shots=three_pointers,
        accent="#A78BFA",
    )

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 440" '
        'role="img" aria-label="Basketball half-court shooting percentages" '
        'style="width:100%;max-width:620px;height:auto;display:block;margin:0 auto;'
        'font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;">\n'
        f"<title>Court Shot Breakdown — {safe_scope}</title>\n"
        "<defs>\n"
        '  <linearGradient id="court-floor" x1="0" y1="0" x2="0" y2="1">\n'
        '    <stop offset="0%" stop-color="#111C30" />\n'
        '    <stop offset="100%" stop-color="#0C1424" />\n'
        "  </linearGradient>\n"
        '  <linearGradient id="paint-fill" x1="0" y1="0" x2="0" y2="1">\n'
        '    <stop offset="0%" stop-color="#1B2D4F" />\n'
        '    <stop offset="100%" stop-color="#15233E" />\n'
        "  </linearGradient>\n"
        "</defs>\n"
        '<rect x="1" y="1" width="558" height="438" rx="14" fill="#0F172A" stroke="#26344D" stroke-width="1.5" />\n'
        f'<text x="24" y="26" fill="#F8FAFC" font-size="14" font-weight="700">{safe_scope}</text>\n'
        f'<text x="536" y="26" text-anchor="end" fill="#94A3B8" font-size="11.5" font-weight="600">{safe_subtitle}</text>\n'
        '<rect x="24" y="46" width="512" height="370" rx="8" fill="url(#court-floor)" stroke="#475569" stroke-width="2" />\n'
        '<path d="M 224 416 A 56 56 0 0 1 336 416" fill="none" stroke="#334155" stroke-width="2" />\n'
        '<rect x="204" y="46" width="152" height="150" fill="url(#paint-fill)" stroke="#64748B" stroke-width="2" />\n'
        '<g stroke="#475569" stroke-width="2">\n'
        '  <line x1="196" y1="100" x2="204" y2="100" /><line x1="356" y1="100" x2="364" y2="100" />\n'
        '  <line x1="196" y1="126" x2="204" y2="126" /><line x1="356" y1="126" x2="364" y2="126" />\n'
        '  <line x1="196" y1="152" x2="204" y2="152" /><line x1="356" y1="152" x2="364" y2="152" />\n'
        "</g>\n"
        '<path d="M 224 196 A 56 56 0 0 0 336 196" fill="none" stroke="#64748B" stroke-width="2" />\n'
        '<path d="M 224 196 A 56 56 0 0 1 336 196" fill="none" stroke="#475569" stroke-width="1.5" stroke-dasharray="6 6" />\n'
        '<line x1="204" y1="196" x2="356" y2="196" stroke="#38BDF8" stroke-opacity="0.75" stroke-width="2.5" />\n'
        '<line x1="60" y1="46" x2="60" y2="156" stroke="#CBD5E1" stroke-opacity="0.7" stroke-width="2.2" />\n'
        '<line x1="500" y1="46" x2="500" y2="156" stroke="#CBD5E1" stroke-opacity="0.7" stroke-width="2.2" />\n'
        '<path d="M 60 156 A 231.5 231.5 0 0 0 500 156" fill="none" stroke="#CBD5E1" stroke-opacity="0.75" stroke-width="2.2" />\n'
        '<path d="M 244 82 A 36 36 0 0 0 316 82" fill="none" stroke="#64748B" stroke-width="1.8" />\n'
        '<line x1="248" y1="68" x2="312" y2="68" stroke="#E2E8F0" stroke-width="3.5" stroke-linecap="round" />\n'
        '<line x1="280" y1="68" x2="280" y2="73" stroke="#F97316" stroke-width="2.5" />\n'
        '<circle cx="280" cy="82" r="9" fill="none" stroke="#F97316" stroke-width="3" />\n'
        f"{empty_banner}"
        f"{ft_badge}\n"
        f"{two_badge}\n"
        f"{three_badge}\n"
        "</svg>"
    )
