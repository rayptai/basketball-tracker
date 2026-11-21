import re

from basketball_tracker.court_svg import render_court_svg
from basketball_tracker.models import ShotTotals


def test_render_court_svg_displays_all_three_zones_and_formatting():
    totals = {
        "Free throws": ShotTotals(8, 10),
        "Two-pointers": ShotTotals(12, 20),
        "Three-pointers": ShotTotals(0, 0),
    }
    svg = render_court_svg(
        totals,
        scope_label="Ray",
        session_count=2,
        date_label="2020-01-01 to 2020-01-02",
    )
    assert svg.startswith("<svg ")
    assert svg.endswith("</svg>")
    assert 'data-zone="free-throws"' in svg
    assert 'data-zone="two-pointers"' in svg
    assert 'data-zone="three-pointers"' in svg
    assert "80.0%" in svg and "8 / 10" in svg
    assert "60.0%" in svg and "12 / 20" in svg
    assert "N/A" in svg and "0 / 0" in svg
    assert "2020-01-01 to 2020-01-02 • 2 sessions" in svg
    assert 'data-empty="true"' not in svg


def test_court_zone_badges_are_ordered_from_ft_line_to_three_point_arc():
    totals = {
        "Free throws": ShotTotals(1, 1),
        "Two-pointers": ShotTotals(1, 1),
        "Three-pointers": ShotTotals(1, 1),
    }
    svg = render_court_svg(totals, scope_label="Ray", session_count=1)
    zone_y = {}
    for zone in ("free-throws", "two-pointers", "three-pointers"):
        match = re.search(rf'data-zone="{zone}".*?<rect[^>]*y="(\d+)"', svg, re.DOTALL)
        assert match is not None
        zone_y[zone] = int(match.group(1))
    assert zone_y["free-throws"] < zone_y["two-pointers"] < zone_y["three-pointers"]


def test_render_court_svg_empty_state_and_html_escaping():
    svg = render_court_svg(
        {},
        scope_label='<script>alert("x")</script> & Zoë',
        session_count=0,
    )
    assert 'data-empty="true"' in svg
    assert "No sessions recorded" in svg
    assert "<script>" not in svg
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; Zoë" in svg
    # Self-contained offline guarantee: only the standard SVG xmlns URL may appear.
    urls = re.findall(r"https?://[^\s\"']+", svg)
    assert urls == ["http://www.w3.org/2000/svg"]
