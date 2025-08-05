"""
Unit tests for the time service.
"""
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from pond.utils.time_service import TimeService


class TestTimeServiceFormatting:
    """Test time formatting for AI consumption."""

    def test_now_returns_utc_datetime(self):
        """Test that now() returns timezone-aware UTC datetime."""
        service = TimeService()
        current = service.now()

        assert current.tzinfo is not None
        assert current.tzinfo.tzname(current) == "UTC"

    def test_format_date(self):
        """Test formatting date in human-readable format."""
        service = TimeService(timezone="America/Los_Angeles")

        # Use a specific datetime instead of now()
        utc_time = datetime(2025, 8, 4, 14, 3, 0, tzinfo=ZoneInfo("UTC"))
        formatted = service.format_date(utc_time)

        # Should be Monday in LA when it's 14:03 UTC
        assert formatted == "Monday, August 4, 2025"

    def test_format_time(self):
        """Test formatting time in human-readable format."""
        service = TimeService(timezone="America/Los_Angeles")

        # Use a specific datetime instead of now()
        utc_time = datetime(2025, 8, 4, 14, 3, 0, tzinfo=ZoneInfo("UTC"))
        formatted = service.format_time(utc_time)

        # Should be 7:03 AM PDT in LA
        assert formatted == "7:03 a.m. PDT"

    def test_format_age(self):
        """Test formatting relative age of datetime."""
        service = TimeService(timezone="America/Los_Angeles")

        # Test various time differences
        now = datetime(2025, 8, 4, 14, 3, 0, tzinfo=ZoneInfo("UTC"))

        # Seconds ago
        assert service.format_age(now - timedelta(seconds=30), now) == "30 seconds before"
        assert service.format_age(now - timedelta(seconds=1), now) == "a few seconds before"

        # Minutes ago
        assert service.format_age(now - timedelta(minutes=5), now) == "5 minutes before"
        assert service.format_age(now - timedelta(minutes=1), now) == "1 minute before"

        # Hours ago
        assert service.format_age(now - timedelta(hours=3), now) == "3 hours before"
        assert service.format_age(now - timedelta(hours=1), now) == "1 hour before"
        assert service.format_age(now - timedelta(hours=26), now) == "1 day before"

        # Days ago
        assert service.format_age(now - timedelta(days=2), now) == "2 days before"
        assert service.format_age(now - timedelta(days=1), now) == "1 day before"

        # Future times
        assert service.format_age(now + timedelta(hours=1), now) == "1 hour after"
        assert service.format_age(now + timedelta(minutes=30), now) == "30 minutes after"

    def test_format_handles_dst_changes(self):
        """Test formatting handles daylight saving time."""
        service = TimeService(timezone="America/Los_Angeles")

        # Use a winter datetime
        utc_time = datetime(2024, 12, 3, 20, 15, 0, tzinfo=ZoneInfo("UTC"))
        formatted = service.format_time(utc_time)

        # Should be PST in winter, not PDT
        assert formatted == "12:15 p.m. PST"

    def test_format_with_different_timezones(self):
        """Test formatting works with various timezones."""
        utc_time = datetime(2024, 8, 3, 20, 15, 0, tzinfo=ZoneInfo("UTC"))

        # Test multiple timezones for time formatting
        cases = [
            ("America/New_York", "4:15 p.m. EDT"),
            ("Europe/London", "9:15 p.m. BST"),
            ("Asia/Tokyo", "5:15 a.m. JST"),
        ]

        for tz, expected in cases:
            service = TimeService(timezone=tz)
            assert service.format_time(utc_time) == expected


class TestTimeServiceParsing:
    """Test parsing human-friendly time intervals."""

    @pytest.mark.parametrize("interval,expected", [
        # Hours
        ("1 hour", timedelta(hours=1)),
        ("6 hours", timedelta(hours=6)),
        ("24 hours", timedelta(hours=24)),

        # Days
        ("yesterday", timedelta(days=1)),
        ("1 day", timedelta(days=1)),
        ("3 days", timedelta(days=3)),
        ("last week", timedelta(weeks=1)),

        # Minutes
        ("30 minutes", timedelta(minutes=30)),
        ("5 mins", timedelta(minutes=5)),

        # Case insensitive
        ("Last Week", timedelta(weeks=1)),
        ("YESTERDAY", timedelta(days=1)),
    ])
    def test_parse_interval_common_formats(self, interval, expected):
        """Test parsing common interval formats."""
        service = TimeService()
        assert service.parse_interval(interval) == expected

    def test_parse_interval_invalid_format(self):
        """Test handling of invalid interval formats."""
        service = TimeService()

        with pytest.raises(ValueError) as exc:
            service.parse_interval("not a valid interval")

        assert "invalid interval" in str(exc.value).lower()

    @pytest.mark.parametrize("dt_str,expected_hour", [
        # ISO format
        ("2024-08-03T20:15:00Z", 20),
        ("2024-08-03 20:15:00", 20),

        # With UTC offset
        ("2024-08-03T13:15:00-07:00", 13),

        # Just date (assumes midnight)
        ("2024-08-03", 0),
    ])
    def test_parse_datetime_formats(self, dt_str, expected_hour):
        """Test parsing various datetime formats."""
        service = TimeService()
        parsed = service.parse_datetime(dt_str)

        assert parsed.year == 2024
        assert parsed.month == 8
        assert parsed.day == 3
        assert parsed.hour == expected_hour


class TestTimeServiceTimezoneDetection:
    """Test automatic timezone detection."""

    def test_timezone_from_override(self):
        """Test explicit timezone override takes precedence."""
        service = TimeService(timezone="Europe/Paris")
        assert service.timezone == "Europe/Paris"

    def test_timezone_from_environment(self):
        """Test timezone from environment variable."""
        with patch.dict(os.environ, {"POND_TIMEZONE": "Asia/Tokyo"}):
            service = TimeService()
            assert service.timezone == "Asia/Tokyo"

    def test_timezone_from_geoip(self):
        """Test timezone detection from Geo-IP."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "timezone": "America/Chicago"
        }
        mock_response.raise_for_status = MagicMock()

        with patch("pond.utils.time_service.httpx.get", return_value=mock_response):
            service = TimeService(geoip_url="https://ipapi.co/json/")
            detected = service._geoip_timezone()
            assert detected == "America/Chicago"

    def test_geoip_fallback_on_error(self):
        """Test fallback when Geo-IP fails."""
        with patch("pond.utils.time_service.httpx.get", side_effect=Exception("Network error")):
            service = TimeService(geoip_url="https://ipapi.co/json/")
            detected = service._geoip_timezone()
            assert detected is None

    def test_geoip_disabled_when_no_url(self):
        """Test that geoip is skipped when no URL is provided."""
        with patch("pond.utils.time_service.httpx.get") as mock_get:
            service = TimeService(geoip_url=None)
            detected = service._geoip_timezone()
            assert detected is None
            # Should not make any HTTP requests
            mock_get.assert_not_called()

    def test_timezone_precedence(self):
        """Test correct precedence of timezone sources."""
        # Environment should override geo-ip
        with patch.dict(os.environ, {"POND_TIMEZONE": "America/New_York"}):
            with patch("pond.utils.time_service.httpx.get") as mock_get:
                mock_response = MagicMock()
                mock_response.json.return_value = {"timezone": "Europe/London"}
                mock_get.return_value = mock_response
                service = TimeService()
                assert service.timezone == "America/New_York"
                # Should not even call geoip when env is set
                mock_get.assert_not_called()

        # Geoip should override system
        with patch.dict(os.environ, {}, clear=True):  # Clear POND_TIMEZONE
            with patch("pond.utils.time_service.httpx.get") as mock_get:
                mock_response = MagicMock()
                mock_response.json.return_value = {"timezone": "Europe/London"}
                mock_response.raise_for_status = MagicMock()
                mock_get.return_value = mock_response
                with patch("pendulum.local_timezone") as mock_local:
                    mock_local.return_value.name = "America/Chicago"
                    service = TimeService(geoip_url="https://ipapi.co/json/")
                    assert service.timezone == "Europe/London"

        # Explicit override should win over everything
        with patch.dict(os.environ, {"POND_TIMEZONE": "America/New_York"}):
            service = TimeService(timezone="Asia/Tokyo")
            assert service.timezone == "Asia/Tokyo"


class TestTimeServiceIntegration:
    """Test time service in realistic scenarios."""

    def test_recent_memories_calculation(self):
        """Test calculating time range for recent memories."""
        service = TimeService(timezone="America/Los_Angeles")

        # "last 6 hours" from current time
        interval = service.parse_interval("last 6 hours")
        now = datetime(2024, 8, 3, 20, 15, 0, tzinfo=ZoneInfo("UTC"))
        since = now - interval

        # Format both for display
        assert service.format_time(since) == "7:15 a.m. PDT"
        assert service.format_time(now) == "1:15 p.m. PDT"
