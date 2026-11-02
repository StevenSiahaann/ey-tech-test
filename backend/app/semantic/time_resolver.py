"""
Deterministic Time Window Resolver for Conversational BI Agent.
Resolves natural language time references (MTD, YTD, Last Month, WTD, Q1 2025, etc.)
into concrete start and end dates based on configurable APP_TIMEZONE and AS_OF_DATE.
Includes `is_explicit` flag to distinguish user-specified time windows from default fallbacks.
"""

import calendar
import os
import re
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any
from zoneinfo import ZoneInfo


MONTH_NAME_MAP: Dict[str, int] = {
    "januari": 1, "january": 1, "jan": 1,
    "februari": 2, "february": 2, "feb": 2,
    "maret": 3, "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mei": 5, "may": 5,
    "juni": 6, "june": 6, "jun": 6,
    "juli": 7, "july": 7, "jul": 7,
    "agustus": 8, "august": 8, "agu": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "october": 10, "okt": 10, "oct": 10,
    "november": 11, "nov": 11,
    "desember": 12, "december": 12, "des": 12, "dec": 12,
}

MONTH_LABELS_ID: Dict[int, str] = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}


def get_app_timezone() -> str:
    """Returns application default timezone."""
    from backend.app.core.config import settings
    return settings.APP_TIMEZONE or os.getenv("APP_TIMEZONE", "Asia/Jakarta")


def get_as_of_date() -> date:
    """Returns the effective date for 'today' in APP_TIMEZONE (or AS_OF_DATE anchor)."""
    from backend.app.core.config import settings
    env_date = settings.AS_OF_DATE or os.getenv("AS_OF_DATE")
    if env_date:
        try:
            return datetime.strptime(str(env_date).strip(), "%Y-%m-%d").date()
        except ValueError:
            pass
    try:
        return datetime.now(ZoneInfo(get_app_timezone())).date()
    except Exception:
        return date.today()


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

    # 1. Specific Quarter with or without Year (e.g., "Q1 2025", "kuartal 1 2025", "Q3")
    q_match = re.search(r'\b(q[1-4]|kuartal\s*[1-4]|quarter\s*[1-4])(?:\s*(20\d{2}))?\b', t)
    if q_match:
        q_str = q_match.group(1).replace("kuartal", "q").replace("quarter", "q").replace(" ", "").upper()
        q_num = int(q_str[1])
        year = int(q_match.group(2)) if q_match.group(2) else today.year

        q_starts = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}
        q_ends = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}

        start = date(year, q_starts[q_num][0], q_starts[q_num][1])
        end = min(date(year, q_ends[q_num][0], q_ends[q_num][1]), today) if (year == today.year and date(year, q_ends[q_num][0], q_ends[q_num][1]) > today and start <= today) else date(year, q_ends[q_num][0], q_ends[q_num][1])
        return TimeWindow(
            start_date=start,
            end_date=end,
            label=f"Q{q_num} {year}",
            assumption_text=f"Rentang Q{q_num} {year}: {start.strftime('%d %b %Y')} s.d. {end.strftime('%d %b %Y')} ({tz})",
            is_explicit=True
        )

    # 1a. Specific Named Month (e.g., "Agustus 2026", "bulan Agustus", "September 2025")
    month_pattern = r'\b(?:' + '|'.join(sorted(MONTH_NAME_MAP.keys(), key=len, reverse=True)) + r')\b(?:\s*(20\d{2}))?'
    m_month = re.search(month_pattern, t)
    if m_month:
        matched_word = m_month.group(0).split()[0].lower()
        m_num = MONTH_NAME_MAP.get(matched_word)
        if m_num:
            m_year = int(m_month.group(1)) if m_month.group(1) else today.year
            last_day = calendar.monthrange(m_year, m_num)[1]
            start = date(m_year, m_num, 1)
            end = today if (m_year == today.year and m_num == today.month) else date(m_year, m_num, last_day)
            m_label = f"{MONTH_LABELS_ID[m_num]} {m_year}"
            return TimeWindow(
                start_date=start,
                end_date=end,
                label=m_label,
                assumption_text=f"Periode {m_label}: {start.strftime('%d %b %Y')} s.d. {end.strftime('%d %b %Y')} ({tz})",
                is_explicit=True
            )

    # 1b. N Months Ago (e.g., "2 bulan lalu", "3 bulan lalu", "2 months ago")
    n_months_match = re.search(r'\b(\d+)\s*(?:bulan|month)s?\s*(?:lalu|ago|terakhir)\b', t)
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
    if re.search(r'(?<!\d\s)\b(?:bulan\s+lalu|bulan\s+kemarin|last\s+month|previous\s+month|past\s+month)\b', t):
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

    # 2b. Previous Year ("tahun lalu", "tahun kemarin", "last year", "previous year")
    if re.search(r'\b(?:tahun\s+lalu|tahun\s+kemarin|last\s+year|previous\s+year)\b', t):
        prev_year = today.year - 1
        start = date(prev_year, 1, 1)
        end = date(prev_year, 12, 31)
        return TimeWindow(
            start_date=start,
            end_date=end,
            label=f"Tahun Lalu ({prev_year})",
            assumption_text=f"Tahun lalu ({prev_year}): {start.strftime('%d %b %Y')} s.d. {end.strftime('%d %b %Y')} ({tz})",
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

    # 4b. Previous Week ("minggu lalu", "pekan lalu", "last week", "previous week")
    if re.search(r'(?<!\d\s)\b(?:minggu\s+lalu|pekan\s+lalu|minggu\s+kemarin|last\s+week|previous\s+week)\b', t):
        this_monday = today - timedelta(days=today.weekday())
        start = this_monday - timedelta(days=7)
        end = this_monday - timedelta(days=1)
        return TimeWindow(
            start_date=start,
            end_date=end,
            label="Minggu Lalu",
            assumption_text=f"Minggu lalu (Senin–Minggu): {start.strftime('%d %b %Y')} s.d. {end.strftime('%d %b %Y')} ({tz})",
            is_explicit=True
        )

    # 4c. N Weeks Ago / Last N Weeks ("2 minggu terakhir", "last 2 weeks")
    n_weeks_match = re.search(r'\b(\d+)\s*(?:minggu|pekan|week)s?\s*(?:terakhir|lalu|ago)\b|\b(?:last|past)\s+(\d+)\s*weeks?\b', t)
    if n_weeks_match:
        n_w = int(n_weeks_match.group(1) or n_weeks_match.group(2))
        start = today - timedelta(days=max(1, n_w * 7 - 1))
        return TimeWindow(
            start_date=start,
            end_date=today,
            label=f"{n_w} Minggu Terakhir",
            assumption_text=f"Periode {n_w} minggu terakhir: {start.strftime('%d %b %Y')} s.d. {today.strftime('%d %b %Y')} ({tz})",
            is_explicit=True
        )

    # 5. Last N Days / Seminggu Terakhir ("7 hari terakhir", "last 7 days", "30 hari terakhir", "seminggu terakhir")
    # Note: "7-day average" is a rolling metric baseline, NOT a time filter!
    n_days_match = re.search(r'\b(\d+)\s*hari\s+terakhir\b|\b(?:last|past)\s+(\d+)\s+days\b', t)
    if n_days_match or re.search(r'\bseminggu\s+terakhir\b', t):
        n_d = int(n_days_match.group(1) or n_days_match.group(2)) if n_days_match else 7
        start = today - timedelta(days=max(0, n_d - 1))
        return TimeWindow(
            start_date=start,
            end_date=today,
            label=f"{n_d} Hari Terakhir",
            assumption_text=f"Periode {n_d} hari kalender terakhir (inklusif): {start.strftime('%d %b %Y')} s.d. {today.strftime('%d %b %Y')} ({tz})",
            is_explicit=True
        )

    # 5b. Yesterday / Today ("kemarin", "yesterday", "hari ini", "today")
    if re.search(r'(?<!bulan\s)(?<!minggu\s)(?<!tahun\s)\b(?:kemarin|yesterday)\b', t):
        yest = today - timedelta(days=1)
        return TimeWindow(
            start_date=yest,
            end_date=yest,
            label="Kemarin",
            assumption_text=f"Tanggal kemarin: {yest.strftime('%d %b %Y')} ({tz})",
            is_explicit=True
        )
    if re.search(r'\b(?:hari\s+ini|today)\b', t):
        return TimeWindow(
            start_date=today,
            end_date=today,
            label="Hari Ini",
            assumption_text=f"Tanggal hari ini: {today.strftime('%d %b %Y')} ({tz})",
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
