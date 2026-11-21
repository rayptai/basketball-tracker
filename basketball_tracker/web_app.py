"""Dark-themed Streamlit web dashboard for the basketball shooting tracker."""

import argparse
from collections.abc import Sequence
from datetime import date, timedelta
from html import escape
import os
from pathlib import Path
import sys

import altair as alt
import pandas as pd
import streamlit as st

from basketball_tracker.court_svg import render_court_svg
from basketball_tracker.dashboard import (
    DATE_PRESETS,
    DATE_PRESET_ALL,
    DATE_PRESET_CUSTOM,
    SCOPE_ALL,
    SCOPE_DEFAULT,
    SCOPE_PLAYER,
    TREND_SERIES,
    DateRange,
    build_history_rows,
    build_trend_points,
    filter_sessions,
    known_players,
    load_dashboard_state,
    record_session,
    resolve_date_range,
    resolve_player_scope,
    summarize_sessions,
    update_default_player,
)
from basketball_tracker.models import format_percentage


SERIES_COLORS = {
    "Overall": "#F97316",
    "Free throws": "#38BDF8",
    "Two-pointers": "#34D399",
    "Three-pointers": "#A78BFA",
}

DARK_ANALYTICS_CSS = """
<style>
.stApp {
  background-color: #0B1120;
  color: #F8FAFC;
}
[data-testid="stSidebar"] {
  background-color: #101829;
  border-right: 1px solid #26344D;
}
[data-testid="stVerticalBlockBorderWrapper"] {
  background-color: #131C2E;
  border-color: #26344D !important;
  border-radius: 12px;
}
[data-testid="stMetric"] {
  background-color: #131C2E;
  padding: 0.25rem 0.25rem 0.1rem 0.25rem;
}
[data-testid="stMetricLabel"] p {
  color: #94A3B8;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
[data-testid="stMetricValue"] {
  color: #F8FAFC;
  font-size: 1.95rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}
.bt-header-bar {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  padding: 0.9rem 1.15rem;
  margin-bottom: 1rem;
  background: linear-gradient(135deg, #131C2E 0%, #18243A 100%);
  border: 1px solid #26344D;
  border-radius: 12px;
}
.bt-title {
  margin: 0;
  font-size: 1.55rem;
  font-weight: 800;
  letter-spacing: 0.01em;
  color: #F8FAFC;
}
.bt-subtitle {
  margin: 0.2rem 0 0 0;
  font-size: 0.88rem;
  color: #94A3B8;
}
.bt-scope-pill {
  padding: 0.35rem 0.8rem;
  border-radius: 999px;
  background-color: rgba(249, 115, 22, 0.14);
  border: 1px solid rgba(249, 115, 22, 0.45);
  color: #FDBA74;
  font-size: 0.84rem;
  font-weight: 700;
}
.bt-kpi-sub {
  color: #94A3B8;
  font-size: 0.82rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  margin-top: -0.35rem;
}
</style>
"""


def resolve_app_paths(argv: Sequence[str] | None = None) -> tuple[Path, Path]:
    """Resolve settings and CSV paths from CLI args, environment overrides, or defaults."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--settings-file", type=Path, default=None)
    parser.add_argument("--data-file", type=Path, default=None)
    parsed, _ = parser.parse_known_args(list(sys.argv[1:]) if argv is None else list(argv))

    env_settings = os.environ.get("BASKETBALL_TRACKER_SETTINGS_FILE")
    env_data = os.environ.get("BASKETBALL_TRACKER_DATA_FILE")

    settings_path = (
        parsed.settings_file
        if parsed.settings_file is not None
        else (Path(env_settings) if env_settings else Path("data/settings.json"))
    )
    data_path = (
        parsed.data_file
        if parsed.data_file is not None
        else (Path(env_data) if env_data else Path("data/sessions.csv"))
    )
    return settings_path, data_path


def _build_trend_chart(points: list[dict[str, object]], active_series: list[str]) -> alt.Chart:
    frame = pd.DataFrame(points)
    color_scale = alt.Scale(
        domain=active_series,
        range=[SERIES_COLORS[name] for name in active_series],
    )
    return (
        alt.Chart(frame)
        .mark_line(point=alt.OverlayMarkDef(filled=True, size=70), strokeWidth=2.5)
        .encode(
            x=alt.X(
                "Date:T",
                title="Session Date",
                axis=alt.Axis(
                    format="%b %d",
                    labelColor="#94A3B8",
                    titleColor="#CBD5E1",
                    gridColor="#1E293B",
                    domainColor="#334155",
                    tickColor="#334155",
                ),
            ),
            y=alt.Y(
                "Percentage:Q",
                title="Shooting %",
                scale=alt.Scale(domain=[0, 100]),
                axis=alt.Axis(
                    labelColor="#94A3B8",
                    titleColor="#CBD5E1",
                    gridColor="#1E293B",
                    domainColor="#334155",
                    tickColor="#334155",
                ),
            ),
            color=alt.Color(
                "Category:N",
                scale=color_scale,
                legend=alt.Legend(
                    orient="top",
                    title=None,
                    labelColor="#E2E8F0",
                    symbolStrokeWidth=3,
                ),
            ),
            tooltip=[
                alt.Tooltip("DateLabel:N", title="Date"),
                alt.Tooltip("Category:N", title="Series"),
                alt.Tooltip("PercentageLabel:N", title="Shooting %"),
                alt.Tooltip("MakesAttempts:N", title="Makes / Attempts"),
                alt.Tooltip("Sessions:Q", title="Sessions on date"),
            ],
        )
        .properties(height=300, background="#131C2E")
        .configure_view(stroke="#26344D", fill="#0F172A")
    )


def render_dashboard(
    settings_path: Path,
    data_path: Path,
    *,
    today: date | None = None,
) -> None:
    """Render the complete dark sports-analytics Streamlit dashboard."""
    current_date = today if today is not None else date.today()
    st.set_page_config(
        page_title="Basketball Shooting Tracker",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(DARK_ANALYTICS_CSS, unsafe_allow_html=True)

    state = load_dashboard_state(settings_path, data_path)
    players = known_players(state.sessions, state.default_player)

    with st.sidebar:
        st.header("Analytics Controls")

        st.subheader("Player Scope")
        default_option_label = (
            f"Default player ({state.default_player})"
            if state.default_player is not None
            else "Default player (not configured)"
        )
        scope_labels = {
            SCOPE_DEFAULT: default_option_label,
            SCOPE_PLAYER: "Specific player",
            SCOPE_ALL: "All players (combined)",
        }
        scope_mode = st.radio(
            "Select scope",
            options=[SCOPE_DEFAULT, SCOPE_PLAYER, SCOPE_ALL],
            format_func=lambda key: scope_labels[key],
            key="scope_mode",
            label_visibility="collapsed",
        )

        selected_player: str | None = None
        if scope_mode == SCOPE_PLAYER:
            dropdown_choice = ""
            if players:
                dropdown_choice = st.selectbox(
                    "Recorded players",
                    options=players,
                    key="specific_player_select",
                )
            custom_player = st.text_input(
                "Or enter exact player name (case-sensitive)",
                value="",
                key="specific_player_custom",
                placeholder="Leave blank to use dropdown selection",
            )
            selected_player = custom_player if custom_player.strip() else dropdown_choice

        st.divider()
        st.subheader("Date Range Filter")
        date_preset = st.selectbox(
            "Date range preset",
            options=list(DATE_PRESETS),
            index=0,
            key="date_range_preset",
            label_visibility="collapsed",
        )

        custom_start: date | None = None
        custom_end: date | None = None
        if date_preset == DATE_PRESET_CUSTOM:
            earliest_date = (
                min(session.date for session in state.sessions)
                if state.sessions
                else current_date - timedelta(days=29)
            )
            custom_start = st.date_input(
                "Start date",
                value=min(earliest_date, current_date),
                max_value=current_date,
                key="custom_start_date",
            )
            custom_end = st.date_input(
                "End date",
                value=current_date,
                max_value=current_date,
                key="custom_end_date",
            )

        st.divider()
        st.subheader("Default Player Settings")
        st.caption(f"Current default: {state.default_player or '(not configured)'}")
        with st.form("default_player_form", clear_on_submit=False):
            new_default_input = st.text_input(
                "Default player name",
                value=state.default_player or "",
                placeholder="e.g. Ray",
                key="default_player_input",
            )
            save_default_clicked = st.form_submit_button(
                "Save Default Player",
                use_container_width=True,
                disabled=state.settings_error is not None,
            )
        if save_default_clicked:
            try:
                saved_name = update_default_player(settings_path, new_default_input)
            except (ValueError, OSError) as error:
                st.error(str(error))
            else:
                previous_default = state.default_player or ""
                if st.session_state.get("add_session_player", "") in ("", previous_default):
                    st.session_state["add_session_player"] = saved_name
                st.session_state["flash_success"] = f"Default player saved: {saved_name}."
                st.rerun()

        st.divider()
        with st.expander("Data paths (read-only)", expanded=False):
            st.caption("Settings file")
            st.code(str(settings_path), language=None)
            st.caption("Sessions CSV")
            st.code(str(data_path), language=None)

    scope = resolve_player_scope(
        scope_mode,
        default_player=state.default_player,
        selected_player=selected_player,
    )

    date_range_error: str | None = None
    try:
        date_range = resolve_date_range(
            date_preset,
            start_date=custom_start,
            end_date=custom_end,
            today=current_date,
        )
    except ValueError as error:
        date_range_error = str(error)
        date_range = DateRange(start=None, end=None, label="Invalid range")

    filtered_sessions = (
        []
        if state.sessions_error is not None or date_range_error is not None
        else filter_sessions(state.sessions, scope, date_range)
    )
    category_totals, overall_totals = summarize_sessions(filtered_sessions)

    session_count = len(filtered_sessions)
    session_word = "session" if session_count == 1 else "sessions"
    st.markdown(
        '<div class="bt-header-bar">'
        "<div>"
        '<h1 class="bt-title">Basketball Shooting Tracker</h1>'
        f'<p class="bt-subtitle">Active view: {escape(scope.label)} &bull; '
        f"Date range: {escape(date_range.label)} &bull; {session_count} {session_word}</p>"
        "</div>"
        f'<div class="bt-scope-pill">Scope: {escape(scope.label)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    flash_success = st.session_state.pop("flash_success", None)
    if flash_success:
        st.success(flash_success)

    if state.settings_error is not None:
        st.error(state.settings_error)
    if state.sessions_error is not None:
        st.error(state.sessions_error)
    if date_range_error is not None:
        st.error(date_range_error)
    elif not scope.is_ready and scope.notice is not None:
        st.info(scope.notice)

    kpi_cards = [
        ("Sessions", str(session_count), date_range.label),
        (
            "Overall",
            format_percentage(overall_totals.percentage),
            f"{overall_totals.makes} / {overall_totals.attempts}",
        ),
        (
            "Free Throws",
            format_percentage(category_totals["Free throws"].percentage),
            f"{category_totals['Free throws'].makes} / {category_totals['Free throws'].attempts}",
        ),
        (
            "Two-Pointers",
            format_percentage(category_totals["Two-pointers"].percentage),
            f"{category_totals['Two-pointers'].makes} / {category_totals['Two-pointers'].attempts}",
        ),
        (
            "Three-Pointers",
            format_percentage(category_totals["Three-pointers"].percentage),
            f"{category_totals['Three-pointers'].makes} / {category_totals['Three-pointers'].attempts}",
        ),
    ]
    kpi_columns = st.columns(len(kpi_cards), gap="small")
    for column, (label, value, subtext) in zip(kpi_columns, kpi_cards, strict=True):
        with column:
            with st.container(border=True):
                st.metric(label=label, value=value)
                st.markdown(f'<div class="bt-kpi-sub">{escape(subtext)}</div>', unsafe_allow_html=True)

    court_column, form_column = st.columns([1.35, 1.0], gap="medium")

    with court_column:
        with st.container(border=True):
            st.subheader("Court Breakdown")
            court_svg = render_court_svg(
                category_totals,
                scope_label=scope.label,
                session_count=session_count,
                date_label=date_range.label,
            )
            st.markdown(court_svg, unsafe_allow_html=True)

    with form_column:
        with st.container(border=True):
            st.subheader("Record Session")
            with st.form("add_session_form", clear_on_submit=False):
                session_date = st.date_input(
                    "Session date",
                    value=current_date,
                    max_value=current_date,
                    key="add_session_date",
                )
                player_input = st.text_input(
                    "Player",
                    value=state.default_player or "",
                    placeholder="Enter player name",
                    help="Overrides the default player for this session without changing settings.",
                    key="add_session_player",
                )

                ft_col1, ft_col2 = st.columns(2)
                ft_makes = ft_col1.number_input("Free throws made", min_value=0, step=1, value=0, key="ft_makes")
                ft_attempts = ft_col2.number_input("Free throws att.", min_value=0, step=1, value=0, key="ft_attempts")

                two_col1, two_col2 = st.columns(2)
                two_makes = two_col1.number_input("Two-pointers made", min_value=0, step=1, value=0, key="two_makes")
                two_attempts = two_col2.number_input("Two-pointers att.", min_value=0, step=1, value=0, key="two_attempts")

                three_col1, three_col2 = st.columns(2)
                three_makes = three_col1.number_input("Three-pointers made", min_value=0, step=1, value=0, key="three_makes")
                three_attempts = three_col2.number_input(
                    "Three-pointers att.", min_value=0, step=1, value=0, key="three_attempts"
                )

                save_session_clicked = st.form_submit_button(
                    "Save Session",
                    type="primary",
                    use_container_width=True,
                    disabled=state.sessions_error is not None,
                )

            if save_session_clicked:
                try:
                    saved = record_session(
                        data_path,
                        session_date=session_date,
                        player_name=player_input,
                        free_throw_makes=int(ft_makes),
                        free_throw_attempts=int(ft_attempts),
                        two_point_makes=int(two_makes),
                        two_point_attempts=int(two_attempts),
                        three_point_makes=int(three_makes),
                        three_point_attempts=int(three_attempts),
                    )
                except (ValueError, OSError) as error:
                    st.error(str(error))
                else:
                    st.session_state["flash_success"] = (
                        f"Saved session for {saved.player_name} on {saved.date.isoformat()}."
                    )
                    st.rerun()

    with st.container(border=True):
        st.subheader("Shooting Percentage Trend Over Time")
        selected_series = st.multiselect(
            "Visible series",
            options=list(TREND_SERIES),
            default=list(TREND_SERIES),
            key="trend_series_select",
        )
        all_points = build_trend_points(filtered_sessions)
        visible_points = [point for point in all_points if point.category in selected_series]
        if not filtered_sessions:
            st.info("No sessions recorded in the selected range.")
        elif not selected_series:
            st.info("Select at least one series to display the trend chart.")
        elif not visible_points:
            st.info("No practiced shots for the selected series in this range.")
        else:
            chart_rows = [
                {
                    "Date": point.session_date.isoformat(),
                    "DateLabel": point.date_label,
                    "Category": point.category,
                    "Percentage": point.percentage,
                    "PercentageLabel": point.percentage_label,
                    "MakesAttempts": point.makes_attempts_label,
                    "Sessions": point.session_count,
                }
                for point in visible_points
            ]
            ordered_series = [name for name in TREND_SERIES if name in selected_series]
            st.altair_chart(_build_trend_chart(chart_rows, ordered_series), use_container_width=True)

    with st.container(border=True):
        st.subheader("Session History")
        if not filtered_sessions:
            st.info("No sessions recorded.")
        else:
            st.dataframe(
                build_history_rows(filtered_sessions),
                hide_index=True,
                use_container_width=True,
            )


def main(argv: Sequence[str] | None = None) -> None:
    settings_path, data_path = resolve_app_paths(argv)
    render_dashboard(settings_path, data_path)


if __name__ == "__main__":
    main()
