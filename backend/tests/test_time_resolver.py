import unittest
from datetime import date
from backend.app.semantic.time_resolver import resolve_time_window


class TestTimeResolver(unittest.TestCase):
    def setUp(self):
        # Anchor date: Thursday, 29 October 2026
        self.anchor = date(2026, 10, 29)

    def test_mtd_default(self):
        w = resolve_time_window("GMV MTD untuk region Jawa?", base_date=self.anchor)
        self.assertEqual(w.start_date, date(2026, 10, 1))
        self.assertEqual(w.end_date, date(2026, 10, 29))
        self.assertEqual(w.label, "MTD")

    def test_this_month(self):
        w = resolve_time_window("Cancel rate bulan ini?", base_date=self.anchor)
        self.assertEqual(w.start_date, date(2026, 10, 1))
        self.assertEqual(w.end_date, date(2026, 10, 29))

    def test_last_month(self):
        w = resolve_time_window("Top 5 produk berdasarkan revenue bulan lalu?", base_date=self.anchor)
        self.assertEqual(w.start_date, date(2026, 9, 1))
        self.assertEqual(w.end_date, date(2026, 9, 30))
        self.assertEqual(w.label, "Bulan Lalu")

    def test_quarter_one_2025(self):
        w = resolve_time_window("Channel dengan revenue tertinggi di Q1 2025?", base_date=self.anchor)
        self.assertEqual(w.start_date, date(2025, 1, 1))
        self.assertEqual(w.end_date, date(2025, 3, 31))
        self.assertEqual(w.label, "Q1 2025")

    def test_ytd(self):
        w = resolve_time_window("Segment customer dengan margin tertinggi YTD?", base_date=self.anchor)
        self.assertEqual(w.start_date, date(2026, 1, 1))
        self.assertEqual(w.end_date, date(2026, 10, 29))
        self.assertEqual(w.label, "YTD")

    def test_this_week(self):
        # Thursday 29 Oct 2026 -> Monday is 26 Oct 2026
        w = resolve_time_window("Revenue POS vs E-commerce minggu ini?", base_date=self.anchor)
        self.assertEqual(w.start_date, date(2026, 10, 26))
        self.assertEqual(w.end_date, date(2026, 10, 29))
        self.assertEqual(w.label, "Minggu Ini")

    def test_standalone_years(self):
        # Past year full calendar
        w_2025 = resolve_time_window("Total revenue di tahun 2025", base_date=self.anchor)
        self.assertEqual(w_2025.start_date, date(2025, 1, 1))
        self.assertEqual(w_2025.end_date, date(2025, 12, 31))
        self.assertTrue(w_2025.is_explicit)

        # Current year up to anchor date
        w_2026 = resolve_time_window("Omzet Fashion di Bandung tahun 2026", base_date=self.anchor)
        self.assertEqual(w_2026.start_date, date(2026, 1, 1))
        self.assertEqual(w_2026.end_date, date(2026, 10, 29))
        self.assertTrue(w_2026.is_explicit)


if __name__ == "__main__":
    unittest.main()
