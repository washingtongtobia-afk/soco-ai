"""Calendar and holiday services for conversational monthly planning.

Handles:
- Automatic local month/year detection
- Conversational opening prompt ("What do you have going on for [current month]?")
- Deterministic federal holidays, social media holidays, and industry observances
- Weekly calendar date calculations and suggested posting dates
"""

from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Any
from pydantic import BaseModel

from app.config.industries import get_industry_profile
from app.models.industry import IndustryType


class ObservanceItem(BaseModel):
    """Normalized holiday or observance entry."""
    name: str
    category: str  # "federal_holiday", "social_holiday", "industry_observance"
    month: int
    day: int
    date_str: str
    description: str


# Static and rule-based holidays
FEDERAL_HOLIDAYS_FIXED = {
    (1, 1): ("New Year's Day", "Federal holiday celebrating the start of the year"),
    (6, 19): ("Juneteenth National Independence Day", "Federal holiday commemorating the end of slavery"),
    (7, 4): ("Independence Day", "Federal holiday commemorating the Declaration of Independence"),
    (11, 11): ("Veterans Day", "Federal holiday honoring military veterans"),
    (12, 25): ("Christmas Day", "Federal holiday celebrating Christmas"),
}

SOCIAL_MEDIA_HOLIDAYS_FIXED = {
    (2, 14): ("Valentine's Day", "Social holiday of appreciation and affection"),
    (3, 8): ("International Women's Day", "Global celebration of social and economic achievements"),
    (4, 11): ("National Pet Day", "Engaging social holiday celebrating beloved companions"),
    (4, 22): ("Earth Day", "Environmental sustainability and community stewardship"),
    (7, 17): ("World Emoji Day", "Fun social media engagement day"),
    (8, 17): ("National Nonprofit Day", "Recognizing impact of charitable organizations"),
    (10, 10): ("World Mental Health Day", "Awareness and community support observance"),
    (10, 31): ("Halloween", "Festive cultural celebration"),
    (12, 31): ("New Year's Eve", "Reflections and looking forward to the new year"),
}


def get_current_month_info(ref_date: datetime | date | None = None) -> tuple[int, int, str]:
    """Return (year, month_number, month_name) for local date."""
    if ref_date is None:
        ref_date = datetime.now()
    year = ref_date.year
    month = ref_date.month
    month_name = calendar.month_name[month]
    return year, month, month_name


def format_conversational_opening(month_name: str | None = None) -> str:
    """Format natural returning user greeting.

    Example: 'What do you have going on for November?'
    """
    if month_name is None:
        _, _, month_name = get_current_month_info()
    return f"What do you have going on for {month_name}?"


def get_nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> int:
    """Find day of month for the nth weekday (0=Mon, ..., 6=Sun)."""
    cal = calendar.monthcalendar(year, month)
    match_count = 0
    for week in cal:
        day = week[weekday]
        if day != 0:
            match_count += 1
            if match_count == n:
                return day
    raise ValueError(f"Cannot find {n}-th weekday {weekday} in {year}-{month}")


def get_last_weekday_of_month(year: int, month: int, weekday: int) -> int:
    """Find day of month for the last weekday (e.g. Memorial Day)."""
    cal = calendar.monthcalendar(year, month)
    for week in reversed(cal):
        day = week[weekday]
        if day != 0:
            return day
    raise ValueError(f"Cannot find last weekday {weekday} in {year}-{month}")


def get_floating_federal_holidays(year: int, month: int) -> list[tuple[int, str, str]]:
    """Return floating holidays (day, name, description) for month."""
    results = []
    if month == 1:
        # MLK Day: 3rd Monday
        day = get_nth_weekday_of_month(year, 1, calendar.MONDAY, 3)
        results.append((day, "Martin Luther King Jr. Day", "Federal holiday honoring Dr. King"))
    elif month == 2:
        # Presidents' Day: 3rd Monday
        day = get_nth_weekday_of_month(year, 2, calendar.MONDAY, 3)
        results.append((day, "Presidents' Day", "Federal holiday celebrating Washington and Lincoln"))
    elif month == 5:
        # Memorial Day: Last Monday
        day = get_last_weekday_of_month(year, 5, calendar.MONDAY)
        results.append((day, "Memorial Day", "Federal holiday honoring fallen service members"))
    elif month == 9:
        # Labor Day: 1st Monday
        day = get_nth_weekday_of_month(year, 9, calendar.MONDAY, 1)
        results.append((day, "Labor Day", "Federal holiday recognizing workers and labor movement"))
    elif month == 10:
        # Columbus / Indigenous Peoples Day: 2nd Monday
        day = get_nth_weekday_of_month(year, 10, calendar.MONDAY, 2)
        results.append((day, "Indigenous Peoples' Day / Columbus Day", "Federal holiday commemorating culture and history"))
    elif month == 11:
        # Thanksgiving: 4th Thursday
        day = get_nth_weekday_of_month(year, 11, calendar.THURSDAY, 4)
        results.append((day, "Thanksgiving Day", "Federal holiday of gratitude and gathering"))
        # Small Business Saturday (Saturday after Thanksgiving)
        results.append((day + 2, "Small Business Saturday", "Celebrating local shops and independent businesses"))
        # Giving Tuesday (Tuesday after Thanksgiving = Thanksgiving + 5 days)
        # Only include here if it stays within November; otherwise it appears in December
        tues_day = day + 5
        num_days_nov = calendar.monthrange(year, 11)[1]
        if tues_day <= num_days_nov:
            results.append((tues_day, "Giving Tuesday", "Global day of generosity and nonprofit giving"))
    elif month == 12:
        # Giving Tuesday falls in December when Thanksgiving is on Nov 26 or later
        # Calculate from Thanksgiving in November
        thanksgiving_day = get_nth_weekday_of_month(year, 11, calendar.THURSDAY, 4)
        tues_day = thanksgiving_day + 5
        num_days_nov = calendar.monthrange(year, 11)[1]
        if tues_day > num_days_nov:
            # Spills into December
            dec_day = tues_day - num_days_nov
            results.append((dec_day, "Giving Tuesday", "Global day of generosity and nonprofit giving"))
    return results


def get_month_observances(
    year: int,
    month: int,
    industry: IndustryType | str | None = None,
) -> list[ObservanceItem]:
    """Retrieve all deterministic federal, social, and industry observances for month."""
    items: list[ObservanceItem] = []

    # 1. Fixed Federal Holidays
    for (m, d), (name, desc) in FEDERAL_HOLIDAYS_FIXED.items():
        if m == month:
            items.append(ObservanceItem(
                name=name,
                category="federal_holiday",
                month=month,
                day=d,
                date_str=f"{year}-{month:02d}-{d:02d}",
                description=desc,
            ))

    # 2. Floating Federal & Key Social Holidays
    for d, name, desc in get_floating_federal_holidays(year, month):
        cat = "social_holiday" if "Small Business" in name or "Giving Tuesday" in name else "federal_holiday"
        items.append(ObservanceItem(
            name=name,
            category=cat,
            month=month,
            day=d,
            date_str=f"{year}-{month:02d}-{d:02d}",
            description=desc,
        ))

    # 3. Fixed Social Media Holidays
    for (m, d), (name, desc) in SOCIAL_MEDIA_HOLIDAYS_FIXED.items():
        if m == month:
            # Prevent duplicate if already added
            if not any(it.name == name for it in items):
                items.append(ObservanceItem(
                    name=name,
                    category="social_holiday",
                    month=month,
                    day=d,
                    date_str=f"{year}-{month:02d}-{d:02d}",
                    description=desc,
                ))

    # 4. Industry-Specific Observances
    if industry:
        profile = get_industry_profile(industry)
        for obs in profile.observances:
            if obs.month == month:
                day = obs.day or 15  # Default mid-month if month-long observance
                items.append(ObservanceItem(
                    name=obs.name,
                    category="industry_observance",
                    month=month,
                    day=day,
                    date_str=f"{year}-{month:02d}-{day:02d}",
                    description=obs.description,
                ))

    # Sort deterministically by day
    items.sort(key=lambda x: x.day)
    return items


def assign_day_to_week(day: int) -> int:
    """Map day of month into standard calendar week bucket (1-5)."""
    if day <= 7:
        return 1
    elif day <= 14:
        return 2
    elif day <= 21:
        return 3
    elif day <= 28:
        return 4
    return 5


def get_suggested_dates_for_week(year: int, month: int, week_number: int) -> list[str]:
    """Calculate 2-3 optimal posting dates for given week (e.g. Tue, Thu)."""
    num_days = calendar.monthrange(year, month)[1]
    start_day = (week_number - 1) * 7 + 1
    end_day = min(week_number * 7, num_days)

    suggested = []
    for d in range(start_day, end_day + 1):
        # Prefer Tuesday (1) and Thursday (3) or Friday (4)
        weekday = calendar.weekday(year, month, d)
        if weekday in (calendar.TUESDAY, calendar.THURSDAY):
            suggested.append(f"{year}-{month:02d}-{d:02d}")

    # Fallback if none matched
    if not suggested:
        mid_day = min(start_day + 2, num_days)
        suggested.append(f"{year}-{month:02d}-{mid_day:02d}")

    return suggested
