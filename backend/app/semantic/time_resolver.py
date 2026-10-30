"""
Deterministic Time Window Resolver for Conversational BI Agent.
Resolves natural language time references (MTD, YTD, Last Month, WTD, Q1 2025, etc.)
into concrete start and end dates based on configurable APP_TIMEZONE and AS_OF_DATE.
Includes `is_explicit` flag to distinguish user-specified time windows from default fallbacks.
"""

import os
import re
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any


def get_as_of_date() -> date:
    """Returns the effective date for 'today' (configurable via AS_OF_DATE in .env or settings)."""
    from backend.app.core.config import settings
    env_date = settings.AS_OF_DATE or os.getenv("AS_OF_DATE")
    if env_date:
        try:
            return datetime.strptime(str(env_date).strip(), "%Y-%m-%d").date()
        except ValueError:
            pass
    return date.today()


def get_app_timezone() -> str:
    """Returns application default timezone."""
    return os.getenv("APP_TIMEZONE", "Asia/Jakarta")


class TimeWindow:
    def __init__(
        self,
        start_date: date,
        end_date: date,
        label: str,
        assumption_text: str,
        is_explicit: bool = False
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.label = label
        self.assumption_text = assumption_text
        self.is_explicit = is_explicit

    @property
    def sql_filter(self) -> str:
        return f"order_date >= '{self.start_date.isoformat()}' AND order_date <= '{self.end_date.isoformat()}'"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "label": self.label,
            "assumption": self.assumption_text,
            "sql_condition": self.sql_filter,
            "is_explicit": self.is_explicit
        }


def resolve_time_window(text: str, base_date: Optional[date] = None) -> TimeWindow:
    """
    Parses natural language text (ID / EN) and returns a TimeWindow object.
    Sets `is_explicit=True` when the user explicitly names a time window,
    preventing stale time context from leaking across turns.
    """
    today = base_date or get_as_of_date()
    tz = get_app_timezone()
    t = text.lower().strip()

    # 1. Specific Quarter (e.g., "Q1 2025", "kuartal 1 2025", "quarter 1 2025")
    q_match = re.search(r'\b(q[1-4]|kuartal\s*[1-4]|quarter\s*[1-4])\s*(202[3-9])\b', t)
    if q_match:
        q_str = q_match.group(1).replace("kuartal", "q").replace("quarter", "q").replace(" ", "").upper()
        q_num = int(q_str[1])
        year = int(q_match.group(2))

        q_starts = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}
        q_ends = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}

        start = date(year, q_starts[q_num][0], q_starts[q_num][1])
        end = date(year, q_ends[q_num][0], q_ends[q_num][1])
        return TimeWindow(
            start_date=start,
            end_date=end,
            label=f"Q{q_num} {year}",
            assumption_text=f"Rentang Q{q_num} {year}: {start.strftime('%d %b %Y')} s.d. {end.strftime('%d %b %Y')} ({tz})",
            is_explicit=True
        )

    # 1b. N Months Ago (e.g., "2 bulan lalu", "3 bulan lalu", "2 months ago")
    n_months_match = re.search(r'\b(\d+)\s*(?:bulan|month)s?\s*(?:lalu|ago)\b', t)
    if n_months_match:
        n = int(n_months_match.group(1))
        curr = date(today.year, today.month, 1)
        for _ in range(n):
            curr = (curr - timedelta(days=1)).replace(day=1)
        start = curr
        if start.month == 12:
            next_m = date(start.year + 1, 1, 1)
        else:
            next_m = date(start.year, start.month + 1, 1)
        end = next_m - timedelta(days=1)
        return TimeWindow(
            start_date=start,
            end_date=end,
            label=f"{n} Bulan Lalu",
            assumption_text=f"{n} bulan lalu dihitung untuk kalender penuh: {start.strftime('%d %b %Y')} s.d. {end.strftime('%d %b %Y')} ({tz})",
            is_explicit=True
        )

    # 2. Previous Month ("bulan lalu", "last month", "previous month")
    if re.search(r'(?<!\d\s)\b(?:bulan\s+lalu| bulan\s+kemarin|last\s+month|previous\s+month|past\s+month)\b', t):
        first_of_this_month = date(today.year, today.month, 1)
        last_day_prev_month = first_of_this_month - timedelta(days=1)
        first_day_prev_month = date(last_day_prev_month.year, last_day_prev_month.month, 1)
        return TimeWindow(
            start_date=first_day_prev_month,
            end_date=last_day_prev_month,
            label="Bulan Lalu",
            assumption_text=f"Bulan lalu didefinisikan sebagai satu bulan kalender penuh: {first_day_prev_month.strftime('%d %b %Y')} s.d. {last_day_prev_month.strftime('%d %b %Y')} ({tz})",
            is_explicit=True
        )

    # 3. YTD ("ytd", "year to date", "tahun ini", "this year")
    if re.search(r'\b(?:ytd|year\s+to\s+date|tahun\s+ini|this\s+year)\b', t):
        start = date(today.year, 1, 1)
        return TimeWindow(
            start_date=start,
            end_date=today,
            label="YTD",
            assumption_text=f"Year-to-Date (YTD): 1 Jan {today.year} s.d. {today.strftime('%d %b %Y')} ({tz})",
            is_explicit=True
        )

    # 4. WTD / This Week ("minggu ini", "pekan ini", "this week", "wtd", "week to date")
    if re.search(r'\b(?:minggu\s+ini|pekan\s+ini|this\s+week|wtd|week\s+to\s+date)\b', t):
        start = today - timedelta(days=today.weekday())
        return TimeWindow(
            start_date=start,
            end_date=today,
            label="Minggu Ini",
            assumption_text=f"Minggu ini dihitung dari awal pekan (Senin): {start.strftime('%d %b %Y')} s.d. {today.strftime('%d %b %Y')} ({tz})",
            is_explicit=True
        )

    # 5. Last 7 Days ("7 hari terakhir", "last 7 days", "past 7 days", "seminggu terakhir")
    # Note: "7-day average" is a rolling metric baseline, NOT a time filter!
    if re.search(r'\b(?:7\s+hari\s+terakhir|last\s+7\s+days|past\s+7\s+days|seminggu\s+terakhir)\b', t):
        start = today - timedelta(days=7)
        return TimeWindow(
            start_date=start,
            end_date=today,
            label="7 Hari Terakhir",
            assumption_text=f"Periode 7 hari terakhir: {start.strftime('%d %b %Y')} s.d. {today.strftime('%d %b %Y')} ({tz})",
            is_explicit=True
        )

    # 6. Explicit MTD ("bulan ini", "this month", "mtd", "month to date")
    if re.search(r'\b(?:bulan\s+ini|this\s+month|mtd|month\s+to\s+date)\b', t):
        start = date(today.year, today.month, 1)
        return TimeWindow(
            start_date=start,
            end_date=today,
            label="MTD",
            assumption_text=f"Month-to-Date (MTD): {start.strftime('%d %b %Y')} s.d. {today.strftime('%d %b %Y')} ({tz})",
            is_explicit=True
        )

    # 7. Anomaly default window (90-day lookback: e.g., 2026-08-01 to 2026-10-29) when time is not explicitly specified
    if re.search(r'\b(?:anomali|anomaly|drop\s*>\s*30%|7-day\s+average)\b', t):
        start = today - timedelta(days=89)
        return TimeWindow(
            start_date=start,
            end_date=today,
            label="90 Hari Terakhir",
            assumption_text=f"Evaluasi anomali dalam jendela 90 hari terakhir: {start.strftime('%d %b %Y')} s.d. {today.strftime('%d %b %Y')} ({tz})",
            is_explicit=False
        )

    # 8. Implicit Default: MTD (when no time expression was mentioned)
    start = date(today.year, today.month, 1)
    return TimeWindow(
        start_date=start,
        end_date=today,
        label="MTD",
        assumption_text=f"Month-to-Date (MTD): {start.strftime('%d %b %Y')} s.d. {today.strftime('%d %b %Y')} ({tz})",
        is_explicit=False
    )
