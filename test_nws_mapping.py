"""Tests for NWS → Home Assistant condition mapping and data handling.

Run: python3 test_nws_mapping.py
Or with a zip code to also test live API: python3 test_nws_mapping.py 80304
"""
import sys
import unittest
import json
import re

# Mock homeassistant before any HA-dependent imports
from unittest import mock

ha_mock = mock.MagicMock()
for mod_name in [
    "homeassistant",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.data_entry_flow",
    "homeassistant.helpers",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.components",
    "homeassistant.components.weather",
    "voluptuous",
    "aiohttp",
]:
    sys.modules.setdefault(mod_name, ha_mock)

# Make DataUpdateCoordinator a real base class that supports generic subscript
class _FakeCoordinator:
    def __init__(self, *a, **kw):
        pass
    def __class_getitem__(cls, item):
        return cls
sys.modules["homeassistant.helpers.update_coordinator"].DataUpdateCoordinator = _FakeCoordinator
sys.modules["homeassistant.helpers.update_coordinator"].UpdateFailed = Exception

# Now we can import normally via the package
sys.path.insert(0, ".")

# Import const (no HA deps)
from custom_components.nws_forecast.const import (
    map_nws_condition,
    degrees_to_compass,
    pair_daily_periods,
    build_hourly_forecasts,
    to_fahrenheit,
    parse_wind_speed_text,
    extract_precip_probability,
    CLOUD_COVERAGE_MAP,
    PROBABILITY_PREFIXES,
)

# Patch __init__.py to be a no-op so coordinator's relative import works
import types
pkg = types.ModuleType("custom_components.nws_forecast")
pkg.__path__ = ["custom_components/nws_forecast"]
pkg.__file__ = "custom_components/nws_forecast/__init__.py"
pkg.map_nws_condition = map_nws_condition
pkg.degrees_to_compass = degrees_to_compass
pkg.CLOUD_COVERAGE_MAP = CLOUD_COVERAGE_MAP
sys.modules["custom_components.nws_forecast"] = pkg

# Re-import const into the package module
import custom_components.nws_forecast.const as const_mod
sys.modules["custom_components.nws_forecast.const"] = const_mod

# Now import coordinator
from custom_components.nws_forecast.coordinator import NWSForecastCoordinator


class TestConditionMapping(unittest.TestCase):
    """Test NWS shortForecast → HA condition mapping."""

    # --- Basic conditions ---

    def test_sunny(self):
        self.assertEqual(map_nws_condition("Sunny", True), "sunny")

    def test_clear_day(self):
        self.assertEqual(map_nws_condition("Clear", True), "sunny")

    def test_clear_night(self):
        self.assertEqual(map_nws_condition("Clear", False), "clear-night")

    def test_sunny_night_becomes_clear(self):
        self.assertEqual(map_nws_condition("Sunny", False), "clear-night")

    def test_mostly_sunny(self):
        self.assertEqual(map_nws_condition("Mostly Sunny", True), "sunny")

    def test_mostly_clear_day(self):
        self.assertEqual(map_nws_condition("Mostly Clear", True), "sunny")

    def test_mostly_clear_night(self):
        self.assertEqual(map_nws_condition("Mostly Clear", False), "clear-night")

    def test_fair(self):
        self.assertEqual(map_nws_condition("Fair", True), "sunny")

    # --- Cloudy conditions ---

    def test_partly_cloudy(self):
        self.assertEqual(map_nws_condition("Partly Cloudy", True), "partlycloudy")

    def test_partly_sunny(self):
        self.assertEqual(map_nws_condition("Partly Sunny", True), "partlycloudy")

    def test_mostly_cloudy(self):
        self.assertEqual(map_nws_condition("Mostly Cloudy", True), "cloudy")

    def test_cloudy(self):
        self.assertEqual(map_nws_condition("Cloudy", True), "cloudy")

    def test_overcast(self):
        self.assertEqual(map_nws_condition("Overcast", True), "cloudy")

    # --- Precipitation ---

    def test_rain(self):
        self.assertEqual(map_nws_condition("Rain", True), "rainy")

    def test_rain_showers(self):
        self.assertEqual(map_nws_condition("Rain Showers", True), "rainy")

    def test_drizzle(self):
        self.assertEqual(map_nws_condition("Drizzle", True), "rainy")

    def test_showers(self):
        self.assertEqual(map_nws_condition("Showers", True), "rainy")

    def test_thunderstorm(self):
        self.assertEqual(map_nws_condition("Thunderstorm", True), "lightning-rainy")

    def test_showers_and_thunderstorms(self):
        self.assertEqual(
            map_nws_condition("Showers And Thunderstorms", True), "lightning-rainy"
        )

    # --- Winter ---

    def test_snow(self):
        self.assertEqual(map_nws_condition("Snow", True), "snowy")

    def test_snow_showers(self):
        self.assertEqual(map_nws_condition("Snow Showers", True), "snowy")

    def test_blizzard(self):
        self.assertEqual(map_nws_condition("Blizzard", True), "snowy")

    def test_freezing_rain(self):
        self.assertEqual(map_nws_condition("Freezing Rain", True), "snowy-rainy")

    def test_sleet(self):
        self.assertEqual(map_nws_condition("Sleet", True), "snowy-rainy")

    def test_wintry_mix(self):
        self.assertEqual(map_nws_condition("Wintry Mix", True), "snowy-rainy")

    # --- Atmosphere ---

    def test_fog(self):
        self.assertEqual(map_nws_condition("Fog", True), "fog")

    def test_haze(self):
        self.assertEqual(map_nws_condition("Haze", True), "fog")

    # --- Wind ---

    def test_windy(self):
        self.assertEqual(map_nws_condition("Windy", True), "windy")

    def test_breezy(self):
        self.assertEqual(map_nws_condition("Breezy", True), "windy")

    # --- Compound conditions (the hard ones) ---

    def test_compound_then_split(self):
        """NWS sends 'X then Y' — we take the first clause."""
        result = map_nws_condition(
            "Slight Chance Rain Showers then Mostly Cloudy", True
        )
        self.assertEqual(result, "rainy")

    def test_compound_snow_then_thunderstorms(self):
        result = map_nws_condition(
            "Slight Chance Snow Showers then Showers And Thunderstorms Likely",
            True,
        )
        self.assertEqual(result, "snowy")

    def test_chance_prefix_stripped(self):
        result = map_nws_condition("Chance Rain Showers", True)
        self.assertEqual(result, "rainy")

    def test_slight_chance_prefix_stripped(self):
        result = map_nws_condition("Slight Chance Snow", True)
        self.assertEqual(result, "snowy")

    def test_likely_prefix_stripped(self):
        result = map_nws_condition("Likely Showers And Thunderstorms", True)
        self.assertEqual(result, "lightning-rainy")

    def test_isolated_prefix_stripped(self):
        result = map_nws_condition("Isolated Thunderstorms", True)
        self.assertEqual(result, "lightning-rainy")

    def test_patchy_fog(self):
        result = map_nws_condition("Patchy Fog", True)
        self.assertEqual(result, "fog")

    # --- Keyword ordering (regression) ---

    def test_partly_cloudy_not_cloudy(self):
        """'Partly Cloudy' must match before 'Cloudy'."""
        self.assertEqual(map_nws_condition("Partly Cloudy", True), "partlycloudy")
        self.assertNotEqual(map_nws_condition("Partly Cloudy", True), "cloudy")

    def test_mostly_cloudy_not_plain_cloudy_keyword(self):
        """'Mostly Cloudy' should match its own entry."""
        self.assertEqual(map_nws_condition("Mostly Cloudy", True), "cloudy")

    # --- Edge cases ---

    def test_empty_string_day(self):
        self.assertEqual(map_nws_condition("", True), "sunny")

    def test_empty_string_night(self):
        self.assertEqual(map_nws_condition("", False), "clear-night")

    def test_none_input(self):
        self.assertEqual(map_nws_condition(None, True), "sunny")

    def test_unknown_condition_day(self):
        self.assertEqual(map_nws_condition("Something Weird", True), "sunny")

    def test_unknown_condition_night(self):
        self.assertEqual(map_nws_condition("Something Weird", False), "clear-night")


class TestMETARParsing(unittest.TestCase):
    """Test METAR raw message parsing."""

    def test_basic_metar(self):
        """Parse a typical METAR string."""
        raw = "KBDU 170156Z AUTO 35015G24KT 10SM CLR 07/06 A2981"
        result = NWSForecastCoordinator._parse_metar(raw)

        self.assertEqual(result["temperature"], 7)
        self.assertEqual(result["dewpoint"], 6)
        self.assertAlmostEqual(result["wind_speed"], 15 * 1.852, places=1)
        self.assertAlmostEqual(result["wind_gust"], 24 * 1.852, places=1)
        self.assertEqual(result["wind_direction"], 350)
        self.assertAlmostEqual(result["pressure"], 29.81 * 3386.39, delta=50)

    def test_negative_temps(self):
        """Parse METAR with minus temps (M prefix)."""
        raw = "KDEN 170156Z AUTO 18010KT 10SM OVC M02/M05 A3012"
        result = NWSForecastCoordinator._parse_metar(raw)

        self.assertEqual(result["temperature"], -2)
        self.assertEqual(result["dewpoint"], -5)

    def test_no_gust(self):
        """Parse METAR without gust component."""
        raw = "KBDU 170156Z AUTO 18010KT 10SM CLR 15/08 A2990"
        result = NWSForecastCoordinator._parse_metar(raw)

        self.assertAlmostEqual(result["wind_speed"], 10 * 1.852, places=1)
        self.assertNotIn("wind_gust", result)

    def test_vrb_wind(self):
        """Parse METAR with variable wind direction."""
        raw = "KBDU 170156Z AUTO VRB05KT 10SM CLR 20/10 A2985"
        result = NWSForecastCoordinator._parse_metar(raw)

        self.assertAlmostEqual(result["wind_speed"], 5 * 1.852, places=1)
        self.assertNotIn("wind_direction", result)


class TestWindCompass(unittest.TestCase):
    """Test degrees to compass conversion."""

    def test_north(self):
        self.assertEqual(degrees_to_compass(0), "N")
        self.assertEqual(degrees_to_compass(355), "N")

    def test_east(self):
        self.assertEqual(degrees_to_compass(90), "E")

    def test_south(self):
        self.assertEqual(degrees_to_compass(180), "S")

    def test_west(self):
        self.assertEqual(degrees_to_compass(270), "W")

    def test_none(self):
        self.assertIsNone(degrees_to_compass(None))


class TestCloudCoverage(unittest.TestCase):
    """Test cloud coverage mapping."""

    def test_clear(self):
        self.assertEqual(CLOUD_COVERAGE_MAP["CLR"], 0)

    def test_scattered(self):
        self.assertEqual(CLOUD_COVERAGE_MAP["SCT"], 37)

    def test_broken(self):
        self.assertEqual(CLOUD_COVERAGE_MAP["BKN"], 68)

    def test_overcast(self):
        self.assertEqual(CLOUD_COVERAGE_MAP["OVC"], 100)


# ======================================================================
# Helper to build realistic NWS period dicts for testing
# ======================================================================

from datetime import datetime as _dt, timedelta as _td

# Default number of forecast days for multi-day tests.
# Change this value (1–10) to test different forecast lengths.
FORECAST_DAYS = 10

# Realistic weather patterns for generated multi-day forecasts.
# Each entry: (day_forecast, night_forecast, high, low, precip_day, precip_night)
_WEATHER_CYCLE = [
    ("Sunny",                          "Clear",                    78, 52, None, None),
    ("Mostly Sunny",                   "Partly Cloudy",            75, 50, None, None),
    ("Partly Cloudy",                  "Mostly Cloudy",            70, 48, None, 10),
    ("Slight Chance Rain Showers",     "Chance Rain Showers",      65, 45, 20,   40),
    ("Rain Showers then Thunderstorms","Showers And Thunderstorms",58, 42, 80,   90),
    ("Chance Snow Showers",            "Snow Showers",             38, 25, 50,   70),
    ("Slight Chance Snow Showers then Showers And Thunderstorms Likely",
                                       "Chance Showers And Thunderstorms", 46, 33, 63, 50),
    ("Mostly Cloudy",                  "Partly Cloudy",            62, 40, 10,   None),
    ("Mostly Sunny",                   "Mostly Clear",             72, 48, None, None),
    ("Sunny",                          "Clear",                    80, 55, None, None),
]

_DAY_NAMES = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]


def _make_period(
    name, start, is_day, temp, short_forecast,
    wind_speed="10 mph", wind_dir="N",
    precip=None, precip_value=None,
):
    """Build a realistic NWS forecast period dict."""
    p = {
        "number": 1,
        "name": name,
        "startTime": start,
        "isDaytime": is_day,
        "temperature": temp,
        "temperatureUnit": "F",
        "shortForecast": short_forecast,
        "windSpeed": wind_speed,
        "windDirection": wind_dir,
        "probabilityOfPrecipitation": {"value": precip_value},
    }
    return p


def _generate_forecast_periods(
    num_days: int = FORECAST_DAYS,
    start_with_tonight: bool = False,
) -> list[dict]:
    """Generate realistic NWS forecast periods for num_days days.

    Args:
        num_days: Number of days of forecast data (1–10).
        start_with_tonight: If True, prepend a "Tonight" night-only period
            before the first full day (like NWS does in the evening).

    Returns:
        List of NWS-style period dicts.
    """
    base_date = _dt(2026, 5, 18)  # Monday
    periods = []
    wind_dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "N", "NW"]

    if start_with_tonight:
        tonight = _WEATHER_CYCLE[0]
        periods.append(_make_period(
            name="Tonight",
            start=(base_date - _td(hours=6)).isoformat(),
            is_day=False,
            temp=tonight[3],  # low temp
            short_forecast=tonight[1],
            wind_speed="5 to 10 mph",
            wind_dir="N",
            precip_value=tonight[5],
        ))

    for day_idx in range(num_days):
        weather = _WEATHER_CYCLE[day_idx % len(_WEATHER_CYCLE)]
        day_forecast, night_forecast, high, low, precip_day, precip_night = weather
        day_date = base_date + _td(days=day_idx)
        day_name = _DAY_NAMES[day_date.weekday()]
        wind_dir = wind_dirs[day_idx % len(wind_dirs)]
        wind_mph = 5 + (day_idx * 3) % 20

        # Daytime period
        periods.append(_make_period(
            name=day_name,
            start=day_date.replace(hour=6).isoformat(),
            is_day=True,
            temp=high,
            short_forecast=day_forecast,
            wind_speed=f"{max(5, wind_mph - 5)} to {wind_mph} mph",
            wind_dir=wind_dir,
            precip_value=precip_day,
        ))

        # Nighttime period
        periods.append(_make_period(
            name=f"{day_name} Night",
            start=day_date.replace(hour=18).isoformat(),
            is_day=False,
            temp=low,
            short_forecast=night_forecast,
            wind_speed=f"{wind_mph} mph",
            wind_dir=wind_dir,
            precip_value=precip_night,
        ))

    return periods


class TestDailyPeriodPairing(unittest.TestCase):
    """Test that NWS day/night periods are correctly paired into daily forecasts.

    This is the critical logic for the HA weather card — NWS sends separate
    periods for day and night, but HA expects one entry per day with both
    native_temperature (high) and native_templow (low).

    The number of days tested is controlled by the module-level FORECAST_DAYS
    constant (default 10). Change it to test anywhere from 1–10 days.
    """

    def test_normal_day_night_pair(self):
        """Standard case: Monday (day) + Monday Night → one daily entry."""
        periods = [
            _make_period("Monday", "2026-05-18T06:00:00", True, 72, "Sunny"),
            _make_period("Monday Night", "2026-05-18T18:00:00", False, 48, "Clear"),
        ]
        result = pair_daily_periods(periods)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["native_temperature"], 72)
        self.assertEqual(result[0]["native_templow"], 48)
        self.assertEqual(result[0]["condition"], "sunny")

    def test_starts_with_tonight(self):
        """First period is 'Tonight' (night) — should be standalone entry."""
        periods = [
            _make_period("Tonight", "2026-05-17T18:00:00", False, 39, "Showers And Thunderstorms"),
            _make_period("Monday", "2026-05-18T06:00:00", True, 72, "Sunny"),
            _make_period("Monday Night", "2026-05-18T18:00:00", False, 48, "Clear"),
        ]
        result = pair_daily_periods(periods)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["native_temperature"], 39)
        self.assertEqual(result[0]["native_templow"], 39)
        self.assertEqual(result[0]["condition"], "lightning-rainy")
        self.assertEqual(result[1]["native_temperature"], 72)
        self.assertEqual(result[1]["native_templow"], 48)

    def test_day_without_following_night(self):
        """Day period at end of data with no matching night."""
        periods = [
            _make_period("Monday", "2026-05-18T06:00:00", True, 72, "Sunny"),
            _make_period("Monday Night", "2026-05-18T18:00:00", False, 48, "Clear"),
            _make_period("Tuesday", "2026-05-19T06:00:00", True, 68, "Partly Cloudy"),
        ]
        result = pair_daily_periods(periods)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[1]["native_temperature"], 68)
        self.assertIsNone(result[1]["native_templow"])

    def test_precip_null_maps_to_zero(self):
        """NWS returns {value: null} for 0% precipitation."""
        periods = [
            _make_period("Monday", "2026-05-18T06:00:00", True, 72, "Sunny",
                         precip_value=None),
            _make_period("Monday Night", "2026-05-18T18:00:00", False, 48, "Clear",
                         precip_value=None),
        ]
        result = pair_daily_periods(periods)
        self.assertEqual(result[0]["precipitation_probability"], 0)

    def test_wind_speed_range_parsing(self):
        """Wind speed '5 to 15 mph' should take the max and convert to km/h."""
        periods = [
            _make_period("Monday", "2026-05-18T06:00:00", True, 72, "Sunny",
                         wind_speed="5 to 15 mph"),
            _make_period("Monday Night", "2026-05-18T18:00:00", False, 48, "Clear",
                         wind_speed="10 mph"),
        ]
        result = pair_daily_periods(periods)
        self.assertAlmostEqual(result[0]["native_wind_speed"], 24.1, places=1)

    def test_condition_day_night_flip(self):
        """'Clear' maps to 'sunny' during day, 'clear-night' at night."""
        periods = [
            _make_period("Monday", "2026-05-18T06:00:00", True, 72, "Clear"),
            _make_period("Monday Night", "2026-05-18T18:00:00", False, 48, "Clear"),
        ]
        result = pair_daily_periods(periods)
        self.assertEqual(result[0]["condition"], "sunny")

    # =================================================================
    # Multi-day generated tests (configurable via FORECAST_DAYS)
    # =================================================================

    def test_n_day_forecast_count(self):
        """Generated N-day forecast produces exactly N daily entries."""
        periods = _generate_forecast_periods(FORECAST_DAYS)
        result = pair_daily_periods(periods)
        self.assertEqual(len(result), FORECAST_DAYS,
                         f"Expected {FORECAST_DAYS} daily entries from "
                         f"{len(periods)} periods, got {len(result)}")

    def test_n_day_with_tonight_count(self):
        """Tonight + N days produces N+1 daily entries."""
        periods = _generate_forecast_periods(FORECAST_DAYS, start_with_tonight=True)
        result = pair_daily_periods(periods)
        self.assertEqual(len(result), FORECAST_DAYS + 1,
                         f"Expected {FORECAST_DAYS + 1} entries (tonight + "
                         f"{FORECAST_DAYS} days), got {len(result)}")

    def test_n_day_every_day_has_high(self):
        """Every daily entry must have a non-None native_temperature (high)."""
        periods = _generate_forecast_periods(FORECAST_DAYS)
        result = pair_daily_periods(periods)
        for i, entry in enumerate(result):
            self.assertIsNotNone(
                entry["native_temperature"],
                f"Day {i} missing native_temperature (high)"
            )

    def test_n_day_every_paired_day_has_low(self):
        """Every day/night paired entry must have native_templow."""
        periods = _generate_forecast_periods(FORECAST_DAYS)
        result = pair_daily_periods(periods)
        for i, entry in enumerate(result):
            self.assertIsNotNone(
                entry["native_templow"],
                f"Day {i} missing native_templow (low)"
            )

    def test_n_day_high_always_exceeds_low(self):
        """High temp should always be ≥ low temp for each day."""
        periods = _generate_forecast_periods(FORECAST_DAYS)
        result = pair_daily_periods(periods)
        for i, entry in enumerate(result):
            high = entry["native_temperature"]
            low = entry["native_templow"]
            if high is not None and low is not None:
                self.assertGreaterEqual(
                    high, low,
                    f"Day {i}: high ({high}) < low ({low})"
                )

    def test_n_day_all_conditions_valid(self):
        """Every daily entry must map to a valid HA condition string."""
        valid_conditions = {
            "sunny", "clear-night", "partlycloudy", "cloudy", "rainy",
            "lightning-rainy", "snowy", "snowy-rainy", "fog", "windy",
            "hail", "tornado", "hurricane", "tropical-storm",
        }
        periods = _generate_forecast_periods(FORECAST_DAYS)
        result = pair_daily_periods(periods)
        for i, entry in enumerate(result):
            self.assertIn(
                entry["condition"], valid_conditions,
                f"Day {i}: invalid condition '{entry['condition']}'"
            )

    def test_n_day_all_have_datetime(self):
        """Every entry must have a non-empty datetime."""
        periods = _generate_forecast_periods(FORECAST_DAYS)
        result = pair_daily_periods(periods)
        for i, entry in enumerate(result):
            self.assertTrue(
                entry.get("datetime"),
                f"Day {i}: missing or empty datetime"
            )

    def test_n_day_precip_in_valid_range(self):
        """Precipitation probability must be 0–100 or None."""
        periods = _generate_forecast_periods(FORECAST_DAYS)
        result = pair_daily_periods(periods)
        for i, entry in enumerate(result):
            precip = entry.get("precipitation_probability")
            if precip is not None:
                self.assertGreaterEqual(precip, 0,
                                        f"Day {i}: precip {precip} < 0")
                self.assertLessEqual(precip, 100,
                                     f"Day {i}: precip {precip} > 100")

    def test_n_day_wind_speed_positive(self):
        """Wind speed should be positive when present."""
        periods = _generate_forecast_periods(FORECAST_DAYS)
        result = pair_daily_periods(periods)
        for i, entry in enumerate(result):
            ws = entry.get("native_wind_speed")
            if ws is not None:
                self.assertGreater(ws, 0, f"Day {i}: wind speed {ws} ≤ 0")

    def test_n_day_compound_conditions_resolve(self):
        """Compound NWS conditions (with 'then') must still produce valid HA conditions."""
        valid_conditions = {
            "sunny", "clear-night", "partlycloudy", "cloudy", "rainy",
            "lightning-rainy", "snowy", "snowy-rainy", "fog", "windy",
            "hail", "tornado", "hurricane", "tropical-storm",
        }
        # Use full 10-day cycle which includes compound forecasts
        periods = _generate_forecast_periods(10)
        result = pair_daily_periods(periods)
        for i, entry in enumerate(result):
            self.assertIn(
                entry["condition"], valid_conditions,
                f"Day {i}: compound condition failed → '{entry['condition']}'"
            )

    def test_tonight_entry_has_correct_shape(self):
        """The 'Tonight' standalone entry must have all required fields."""
        periods = _generate_forecast_periods(FORECAST_DAYS, start_with_tonight=True)
        result = pair_daily_periods(periods)

        tonight = result[0]
        required_keys = [
            "datetime", "condition", "native_temperature",
            "native_templow", "precipitation_probability",
            "native_wind_speed", "wind_bearing",
        ]
        for key in required_keys:
            self.assertIn(key, tonight, f"Tonight entry missing '{key}'")

        # Tonight: temp == templow (standalone night)
        self.assertEqual(tonight["native_temperature"], tonight["native_templow"])

    def test_varying_day_counts(self):
        """Pairing works correctly for every count from 1 to 10."""
        for n in range(1, 11):
            with self.subTest(days=n):
                periods = _generate_forecast_periods(n)
                result = pair_daily_periods(periods)
                self.assertEqual(len(result), n,
                                 f"{n}-day forecast produced {len(result)} entries")
                # Verify all have high/low
                for i, entry in enumerate(result):
                    self.assertIsNotNone(entry["native_temperature"],
                                         f"Day {i}/{n}: missing high")
                    self.assertIsNotNone(entry["native_templow"],
                                         f"Day {i}/{n}: missing low")

    def test_varying_day_counts_with_tonight(self):
        """Tonight + N days works for every count from 1 to 10."""
        for n in range(1, 11):
            with self.subTest(days=n):
                periods = _generate_forecast_periods(n, start_with_tonight=True)
                result = pair_daily_periods(periods)
                self.assertEqual(len(result), n + 1,
                                 f"Tonight + {n} days produced {len(result)} entries")


class TestHourlyForecasts(unittest.TestCase):
    """Test hourly forecast conversion to HA format."""

    def test_basic_hourly(self):
        """Convert a few hourly periods."""
        periods = [
            {
                "startTime": "2026-05-18T14:00:00",
                "isDaytime": True,
                "temperature": 72,
                "shortForecast": "Sunny",
                "windSpeed": "10 mph",
                "windDirection": "SW",
                "probabilityOfPrecipitation": {"value": None},
                "dewpoint": {"value": 8.3, "unitCode": "wmoUnit:degC"},
                "relativeHumidity": {"value": 42.5, "unitCode": "wmoUnit:percent"},
            },
            {
                "startTime": "2026-05-18T15:00:00",
                "isDaytime": True,
                "temperature": 74,
                "shortForecast": "Partly Cloudy",
                "windSpeed": "5 to 10 mph",
                "windDirection": "W",
                "probabilityOfPrecipitation": {"value": 20},
                "dewpoint": {"value": 10.0, "unitCode": "wmoUnit:degC"},
                "relativeHumidity": {"value": 38.0, "unitCode": "wmoUnit:percent"},
            },
        ]
        result = build_hourly_forecasts(periods)

        self.assertEqual(len(result), 2)

        # First hour
        self.assertEqual(result[0]["native_temperature"], 72)
        self.assertEqual(result[0]["condition"], "sunny")
        self.assertEqual(result[0]["precipitation_probability"], 0)  # null → 0
        # Dewpoint: 8.3°C → °F = 46.9
        self.assertAlmostEqual(result[0]["native_dew_point"], 46.9, places=1)
        self.assertEqual(result[0]["humidity"], 42.5)

        # Second hour
        self.assertEqual(result[1]["native_temperature"], 74)
        self.assertEqual(result[1]["condition"], "partlycloudy")
        self.assertEqual(result[1]["precipitation_probability"], 20)

    def test_hourly_dewpoint_celsius_to_fahrenheit(self):
        """Dewpoint comes in °C even when temp is °F — must convert."""
        periods = [
            {
                "startTime": "2026-05-18T14:00:00",
                "isDaytime": True,
                "temperature": 72,  # already °F
                "shortForecast": "Sunny",
                "windSpeed": "10 mph",
                "windDirection": "N",
                "probabilityOfPrecipitation": {"value": None},
                "dewpoint": {"value": 0.0, "unitCode": "wmoUnit:degC"},  # 0°C = 32°F
                "relativeHumidity": {"value": 50, "unitCode": "wmoUnit:percent"},
            },
        ]
        result = build_hourly_forecasts(periods)
        self.assertAlmostEqual(result[0]["native_dew_point"], 32.0, places=1)

    def test_hourly_limit(self):
        """Should limit to 48 hours by default."""
        periods = [
            {
                "startTime": f"2026-05-18T{i:02d}:00:00",
                "isDaytime": True,
                "temperature": 70,
                "shortForecast": "Sunny",
                "windSpeed": "5 mph",
                "windDirection": "N",
                "probabilityOfPrecipitation": {"value": None},
            }
            for i in range(60)
        ]
        result = build_hourly_forecasts(periods)
        self.assertEqual(len(result), 48)

    def test_hourly_night_condition(self):
        """Night hours should map 'Clear' to 'clear-night'."""
        periods = [
            {
                "startTime": "2026-05-18T22:00:00",
                "isDaytime": False,
                "temperature": 55,
                "shortForecast": "Clear",
                "windSpeed": "5 mph",
                "windDirection": "N",
                "probabilityOfPrecipitation": {"value": None},
            },
        ]
        result = build_hourly_forecasts(periods)
        self.assertEqual(result[0]["condition"], "clear-night")


class TestPrecipExtraction(unittest.TestCase):
    """Test precipitation probability extraction edge cases."""

    def test_null_value(self):
        self.assertEqual(extract_precip_probability({"value": None}), 0)

    def test_zero_value(self):
        self.assertEqual(extract_precip_probability({"value": 0}), 0)

    def test_normal_value(self):
        self.assertEqual(extract_precip_probability({"value": 83}), 83)

    def test_not_a_dict(self):
        self.assertEqual(extract_precip_probability(42), 0)

    def test_empty_dict(self):
        self.assertEqual(extract_precip_probability({}), 0)


class TestWindSpeedParsing(unittest.TestCase):
    """Test wind speed text parsing."""

    def test_simple(self):
        self.assertAlmostEqual(parse_wind_speed_text("10 mph"), 16.1, places=1)

    def test_range(self):
        # "5 to 15" → takes 15, converts to km/h
        self.assertAlmostEqual(parse_wind_speed_text("5 to 15 mph"), 24.1, places=1)

    def test_empty(self):
        self.assertIsNone(parse_wind_speed_text(""))

    def test_none(self):
        self.assertIsNone(parse_wind_speed_text(None))

    def test_no_numbers(self):
        self.assertIsNone(parse_wind_speed_text("calm"))


class TestTemperatureConversion(unittest.TestCase):
    """Test Fahrenheit conversion from various unit codes."""

    def test_celsius_to_fahrenheit(self):
        # 0°C = 32°F
        self.assertAlmostEqual(to_fahrenheit(0, "wmoUnit:degC"), 32.0, places=1)
        # 100°C = 212°F
        self.assertAlmostEqual(to_fahrenheit(100, "wmoUnit:degC"), 212.0, places=1)

    def test_already_fahrenheit(self):
        self.assertEqual(to_fahrenheit(72, "wmoUnit:degF"), 72.0)

    def test_none_value(self):
        self.assertIsNone(to_fahrenheit(None, "wmoUnit:degC"))

    def test_negative_celsius(self):
        # -40°C = -40°F
        self.assertAlmostEqual(to_fahrenheit(-40, "wmoUnit:degC"), -40.0, places=1)


def run_live_test(zip_code: str):
    """Fetch live NWS data and display the mapping analysis."""
    import urllib.request

    print(f"\n{'='*60}")
    print(f"LIVE NWS API TEST — Zip: {zip_code}")
    print(f"{'='*60}")

    # Resolve zip to lat/lon
    url = f"https://api.zippopotam.us/us/{zip_code}"
    req = urllib.request.Request(url, headers={"User-Agent": "NWS-HA-Test/1.0"})
    try:
        with urllib.request.urlopen(req) as resp:
            geo = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print(f"ERROR: Could not resolve zip {zip_code}")
            return
        raise

    place = geo["places"][0]
    lat, lon = float(place["latitude"]), float(place["longitude"])
    place_name = place.get("place name", zip_code)
    print(f"Location: {place_name} ({lat:.4f}, {lon:.4f})")

    # Get NWS grid
    headers = {"User-Agent": "(HA-NWS-Test, test@example.com)", "Accept": "application/geo+json"}

    url = f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        points = json.loads(resp.read())

    props = points["properties"]
    grid_id = props["gridId"]
    grid_x = props["gridX"]
    grid_y = props["gridY"]
    print(f"NWS Grid: {grid_id} {grid_x},{grid_y}")

    # Fetch forecast
    url = f"https://api.weather.gov/gridpoints/{grid_id}/{grid_x},{grid_y}/forecast"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        forecast = json.loads(resp.read())

    periods = forecast["properties"]["periods"]
    num_periods = len(periods)
    print(f"\n--- ALL RAW NWS PERIODS ({num_periods} total) ---")
    print(f"  {'#':>2} {'Name':20s} | {'Day?':4s} | {'NWS shortForecast':50s} | "
          f"{'Temp':>6} | {'Precip':>6}")
    print(f"  {'-'*2} {'-'*20} + {'-'*4} + {'-'*50} + {'-'*6} + {'-'*6}")
    for idx, p in enumerate(periods):
        short = p.get("shortForecast", "")
        precip = p.get("probabilityOfPrecipitation", {})
        precip_val = precip.get("value") if isinstance(precip, dict) else precip
        is_day = "DAY" if p.get("isDaytime", True) else "NITE"
        temp_str = f"{p.get('temperature')}°{p.get('temperatureUnit', 'F')}"
        precip_str = str(precip_val) if precip_val is not None else "null→0"
        print(f"  {idx+1:2d} {p['name']:20s} | {is_day:4s} | {short:50s} | "
              f"{temp_str:>6} | {precip_str:>6}")

    # ---------------------------------------------------------------
    # Run pair_daily_periods — this is what HA's weather card will see
    # ---------------------------------------------------------------
    daily = pair_daily_periods(periods)
    print(f"\n--- HA DAILY FORECAST (pair_daily_periods → {len(daily)} entries) ---")
    print(f"  This is exactly what Home Assistant's weather card renders.")
    print(f"  {'#':>2} {'Date':20s} | {'Condition':20s} | {'High':>6} | {'Low':>6} | "
          f"{'Precip%':>7} | {'Wind km/h':>9} | {'Wind Dir':>8}")
    print(f"  {'-'*2} {'-'*20} + {'-'*20} + {'-'*6} + {'-'*6} + "
          f"{'-'*7} + {'-'*9} + {'-'*8}")
    for idx, d in enumerate(daily):
        dt = d.get("datetime", "")[:16]
        cond = d.get("condition", "?")
        high = d.get("native_temperature")
        low = d.get("native_templow")
        precip = d.get("precipitation_probability")
        ws = d.get("native_wind_speed")
        wb = d.get("wind_bearing", "")
        high_s = f"{high}°F" if high is not None else "N/A"
        low_s = f"{low}°F" if low is not None else "N/A"
        precip_s = f"{precip}%" if precip is not None else "N/A"
        ws_s = f"{ws:.1f}" if ws is not None else "N/A"
        print(f"  {idx+1:2d} {dt:20s} | {cond:20s} | {high_s:>6} | {low_s:>6} | "
              f"{precip_s:>7} | {ws_s:>9} | {str(wb):>8}")

    # Validate the output
    issues = []
    for idx, d in enumerate(daily):
        if d.get("native_temperature") is None:
            issues.append(f"  Day {idx+1}: missing high temp")
        if d.get("condition") is None:
            issues.append(f"  Day {idx+1}: missing condition")
        high = d.get("native_temperature")
        low = d.get("native_templow")
        if high is not None and low is not None and high < low:
            issues.append(f"  Day {idx+1}: high ({high}) < low ({low})")

    if issues:
        print(f"\n⚠ ISSUES FOUND:")
        for issue in issues:
            print(issue)
    else:
        print(f"\n✓ All {len(daily)} daily entries valid — ready for HA weather card")

    # ---------------------------------------------------------------
    # Fetch hourly forecast and show first 24h as HA would render
    # ---------------------------------------------------------------
    print(f"\n--- Fetching hourly forecast ---")
    url = f"https://api.weather.gov/gridpoints/{grid_id}/{grid_x},{grid_y}/forecast/hourly"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        hourly_data = json.loads(resp.read())

    hourly_periods = hourly_data["properties"]["periods"]
    hourly = build_hourly_forecasts(hourly_periods)

    print(f"\n--- HA HOURLY FORECAST (first 24 of {len(hourly)}) ---")
    print(f"  {'#':>2} {'Time':20s} | {'Condition':20s} | {'Temp':>6} | "
          f"{'Precip%':>7} | {'Dewpt':>6} | {'Humid%':>6}")
    print(f"  {'-'*2} {'-'*20} + {'-'*20} + {'-'*6} + "
          f"{'-'*7} + {'-'*6} + {'-'*6}")
    for idx, h in enumerate(hourly[:24]):
        dt = h.get("datetime", "")[:16]
        cond = h.get("condition", "?")
        temp = h.get("native_temperature")
        precip = h.get("precipitation_probability")
        dew = h.get("native_dew_point")
        hum = h.get("humidity")
        temp_s = f"{temp}°F" if temp is not None else "N/A"
        precip_s = f"{precip}%" if precip is not None else "N/A"
        dew_s = f"{dew:.0f}°F" if dew is not None else "N/A"
        hum_s = f"{hum:.0f}%" if hum is not None else "N/A"
        print(f"  {idx+1:2d} {dt:20s} | {cond:20s} | {temp_s:>6} | "
              f"{precip_s:>7} | {dew_s:>6} | {hum_s:>6}")

    # ---------------------------------------------------------------
    # Fetch observation + METAR fallback
    # ---------------------------------------------------------------
    url = f"https://api.weather.gov/gridpoints/{grid_id}/{grid_x},{grid_y}/stations"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        stations = json.loads(resp.read())

    station_id = stations["features"][0]["id"].split("/")[-1]
    print(f"\n--- CURRENT OBSERVATION (station: {station_id}) ---")

    url = f"https://api.weather.gov/stations/{station_id}/observations/latest"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        obs = json.loads(resp.read())

    obs_props = obs["properties"]
    fields = ["temperature", "dewpoint", "windSpeed", "windDirection",
              "relativeHumidity", "barometricPressure", "visibility"]
    for field in fields:
        val = obs_props.get(field, {})
        if isinstance(val, dict):
            v = val.get('value')
            print(f"  {field:25s} | value: {str(v):>10} | unit: {val.get('unitCode', 'N/A')}")
        else:
            print(f"  {field:25s} | value: {val}")

    raw = obs_props.get("rawMessage", "")
    print(f"  {'rawMessage':25s} | {raw}")

    if raw:
        parsed = NWSForecastCoordinator._parse_metar(raw)
        print(f"\n--- METAR FALLBACK PARSE ---")
        for k, v in parsed.items():
            print(f"  {k:25s} | {v}")

        # Show which fields needed fallback
        null_fields = [f for f in ["temperature", "dewpoint", "windSpeed", "windDirection"]
                       if obs_props.get(f, {}).get("value") is None]
        if null_fields:
            print(f"\n  ⚠ Fields that were NULL and needed METAR fallback: {', '.join(null_fields)}")
        else:
            print(f"\n  ✓ All observation fields had values — METAR fallback not needed")

    # Dump raw data
    dump = {
        "forecast_periods": periods,
        "daily_ha_output": daily,
        "hourly_ha_output": hourly[:24],
        "observation": {k: obs_props.get(k) for k in fields + ["rawMessage", "textDescription", "cloudLayers"]},
    }
    dump_path = "nws_raw_dump.json"
    with open(dump_path, "w") as f:
        json.dump(dump, f, indent=2, default=str)
    print(f"\nFull data saved to {dump_path}")


if __name__ == "__main__":
    # Run unit tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Run live test if zip code provided
    if len(sys.argv) > 1:
        run_live_test(sys.argv[1])

    sys.exit(0 if result.wasSuccessful() else 1)
