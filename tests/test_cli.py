import unittest

from tradebridge.cli import parse_time_milliseconds


class CliTests(unittest.TestCase):
    def test_parse_time_milliseconds_from_epoch_ms(self) -> None:
        self.assertEqual(parse_time_milliseconds("1704067200000"), 1704067200000)

    def test_parse_time_milliseconds_from_date(self) -> None:
        self.assertEqual(parse_time_milliseconds("2024-01-01"), 1704067200000)

    def test_parse_time_milliseconds_from_datetime_z(self) -> None:
        self.assertEqual(parse_time_milliseconds("2024-01-01T00:00:00Z"), 1704067200000)


if __name__ == "__main__":
    unittest.main()
