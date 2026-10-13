"""Unit tests for calendar service, date detection, and holiday mappings."""

from datetime import date
from app.models.industry import IndustryType
from app.planning.calendar_service import (
    assign_day_to_week,
    format_conversational_opening,
    get_current_month_info,
    get_month_observances,
    get_suggested_dates_for_week,
)


def test_conversational_opening_format():
    """Verify natural returning user greeting format."""
    greeting = format_conversational_opening("November")
    assert greeting == "What do you have going on for November?"

    greeting_oct = format_conversational_opening("October")
    assert greeting_oct == "What do you have going on for October?"


def test_local_month_detection():
    """Verify local month/year determination."""
    ref = date(2026, 11, 15)
    year, month, name = get_current_month_info(ref)
    assert year == 2026
    assert month == 11
    assert name == "November"


def test_holiday_selection_november():
    """Verify federal and social holidays in November (Veterans Day, Thanksgiving, Giving Tuesday)."""
    observances = get_month_observances(2026, 11, IndustryType.NONPROFIT)
    names = [o.name for o in observances]

    assert "Veterans Day" in names
    assert "Thanksgiving Day" in names
    assert "Small Business Saturday" in names
    assert "Giving Tuesday" in names
    # Industry observance for nonprofit in Nov:
    assert any("Hunger & Homelessness" in n or "Giving Tuesday" in n for n in names)


def test_weekly_bucketing_and_suggested_dates():
    """Verify dates bucket correctly into weeks and suggested posting dates."""
    assert assign_day_to_week(3) == 1
    assert assign_day_to_week(10) == 2
    assert assign_day_to_week(18) == 3
    assert assign_day_to_week(25) == 4
    assert assign_day_to_week(30) == 5

    suggested = get_suggested_dates_for_week(2026, 11, 2)
    assert len(suggested) >= 1
    assert all(d.startswith("2026-11-") for d in suggested)
