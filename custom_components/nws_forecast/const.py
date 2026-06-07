"""Constants for NWS Weather Forecast integration."""

DOMAIN = "nws_forecast"

CONF_ZIP_CODE = "zip_code"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_GRID_ID = "grid_id"
CONF_GRID_X = "grid_x"
CONF_GRID_Y = "grid_y"
CONF_STATION_ID = "station_id"

DEFAULT_SCAN_INTERVAL = 3600  # 1 hour

NWS_API_BASE = "https://api.weather.gov"
ZIP_API_BASE = "https://api.zippopotam.us/us"

USER_AGENT = "HomeAssistant-NWS-Forecast/1.0.0"

# Cloud coverage mapping from aviation codes to percentages
CLOUD_COVERAGE_MAP = {
    "CLR": 0,
    "SKC": 0,
    "FEW": 18,    # 1/8 - 2/8
    "SCT": 37,    # 3/8 - 4/8
    "BKN": 68,    # 5/8 - 7/8
    "OVC": 100,   # 8/8
    "VV": 100,    # Vertical visibility (obscured)
}

# Probability prefixes to strip from NWS shortForecast strings
# Order matters: longest first to avoid partial matches
PROBABILITY_PREFIXES = [
    "Slight Chance ",
    "Chance ",
    "Likely ",
    "Isolated ",
    "Scattered ",
    "Numerous ",
    "Patchy ",
    "Areas Of ",
    "Widespread ",
]

# NWS condition keyword → HA condition mapping
# ORDER MATTERS: more specific phrases MUST come before generic ones
# e.g., "Partly Cloudy" before "Cloudy", "Freezing Rain" before "Rain"
# Source: https://www.weather.gov/forecast-icons
NWS_TO_HA_CONDITION = [
    # Severe
    ("Tornado", "tornado"),
    ("Water Spout", "tornado"),
    ("Funnel Cloud", "tornado"),
    ("Hurricane", "hurricane"),
    ("Tropical Storm", "tropical-storm"),
    # Ice / hail — before "Snow" so "Snow Pellets" matches here
    ("Small Hail", "hail"),
    ("Snow Pellets", "hail"),
    ("Ice Pellets", "hail"),
    ("Ice Crystals", "hail"),
    ("Hail", "hail"),
    # Winter
    ("Blizzard", "snowy"),
    ("Ice Storm", "snowy"),
    ("Freezing Fog", "fog"),
    ("Freezing Rain", "snowy-rainy"),
    ("Freezing Drizzle", "snowy-rainy"),
    ("Sleet", "snowy-rainy"),
    ("Snow Showers", "snowy"),
    ("Snow Grains", "snowy"),
    ("Blowing Snow", "snowy"),
    ("Low Drifting Snow", "snowy"),
    ("Snow", "snowy"),
    ("Flurries", "snowy"),
    # Rain & storms — specific before generic
    ("Thunderstorm", "lightning-rainy"),
    ("T-storms", "lightning-rainy"),
    ("Showers And Thunderstorms", "lightning-rainy"),
    ("Rain Showers", "rainy"),
    ("Heavy Rain", "pouring"),
    ("Drizzle", "rainy"),
    ("Rain", "rainy"),
    ("Showers", "rainy"),
    # Mixed
    ("Wintry Mix", "snowy-rainy"),
    ("Rain And Snow", "snowy-rainy"),
    # Atmosphere — "Dust Storm" / "Sand Storm" before generic "Dust" / "Sand"
    ("Dust Storm", "fog"),
    ("Sand Storm", "fog"),
    ("Dust/Sand Whirls", "fog"),
    ("Volcanic Ash", "fog"),
    ("Fog", "fog"),
    ("Haze", "fog"),
    ("Smoke", "fog"),
    ("Sand", "fog"),
    ("Dust", "fog"),
    ("Mist", "fog"),
    # Clouds — specific before generic
    ("A Few Clouds", "partlycloudy"),
    ("Mostly Cloudy", "cloudy"),
    ("Partly Cloudy", "partlycloudy"),
    ("Partly Sunny", "partlycloudy"),
    ("Mostly Sunny", "sunny"),
    ("Mostly Clear", "clear-night"),  # overridden by is_daytime
    ("Cloudy", "cloudy"),
    ("Overcast", "cloudy"),
    # Clear / temperature
    ("Sunny", "sunny"),
    ("Clear", "clear-night"),  # overridden by is_daytime
    ("Fair", "sunny"),
    ("Hot", "sunny"),
    ("Cold", "clear-night"),  # overridden by is_daytime
    # Wind
    ("Windy", "windy"),
    ("Breezy", "windy"),
    ("Blustery", "windy"),
]

# METAR wind direction compass mapping
METAR_WIND_DIRECTIONS = {
    range(349, 361): "N",
    range(0, 12): "N",
    range(12, 34): "NNE",
    range(34, 57): "NE",
    range(57, 79): "ENE",
    range(79, 102): "E",
    range(102, 124): "ESE",
    range(124, 147): "SE",
    range(147, 169): "SSE",
    range(169, 192): "S",
    range(192, 214): "SSW",
    range(214, 237): "SW",
    range(237, 259): "WSW",
    range(259, 282): "W",
    range(282, 304): "WNW",
    range(304, 327): "NW",
    range(327, 349): "NNW",
}


def map_nws_condition(short_forecast: str, is_daytime: bool = True) -> str:
    """Map an NWS shortForecast string to a Home Assistant condition.

    Handles compound phrases like 'Slight Chance Rain Showers then Mostly Cloudy'
    by splitting on ' then ' and taking the first (primary) clause.
    Strips probability prefixes before keyword matching.
    Adjusts clear/sunny for day vs night.
    """
    if not short_forecast:
        return "sunny" if is_daytime else "clear-night"

    # Split on " then " and take the first (primary) condition
    primary = short_forecast.split(" then ")[0].strip()

    # Strip probability prefixes
    for prefix in PROBABILITY_PREFIXES:
        if primary.startswith(prefix):
            primary = primary[len(prefix):]
            break

    # Keyword match in priority order
    primary_lower = primary.lower()
    for keyword, ha_condition in NWS_TO_HA_CONDITION:
        if keyword.lower() in primary_lower:
            # Adjust day/night for clear-type conditions
            if ha_condition == "clear-night" and is_daytime:
                return "sunny"
            if ha_condition == "sunny" and not is_daytime:
                return "clear-night"
            return ha_condition

    # Fallback
    return "sunny" if is_daytime else "clear-night"


def degrees_to_compass(degrees: float) -> str:
    """Convert wind direction in degrees to compass bearing."""
    if degrees is None:
        return None
    deg = int(round(degrees)) % 360
    for deg_range, direction in METAR_WIND_DIRECTIONS.items():
        if deg in deg_range:
            return direction
    return "N"


def parse_wind_speed_text(wind_text: str) -> float | None:
    """Parse NWS wind speed text like '5 to 15 mph' or '10 mph'.

    Returns the higher value in km/h.
    """
    if not wind_text:
        return None
    import re

    numbers = re.findall(r"(\d+)", wind_text)
    if not numbers:
        return None

    # Take the highest value (for ranges like "5 to 15")
    max_mph = max(int(n) for n in numbers)

    # Convert mph to km/h
    return round(max_mph * 1.60934, 1)


def extract_precip_probability(precip_field) -> int:
    """Extract precipitation probability from NWS format.

    NWS returns {value: null} when it means 0%, not {value: 0}.
    """
    if isinstance(precip_field, dict):
        val = precip_field.get("value")
        return val if val is not None else 0
    return 0


def pair_daily_periods(periods: list[dict]) -> list[dict]:
    """Pair NWS day/night forecast periods into daily forecast entries.

    NWS returns separate periods for each half-day:
      - "Monday" (isDaytime=True, high temp)
      - "Monday Night" (isDaytime=False, low temp)

    Home Assistant's weather card expects ONE entry per day with both
    native_temperature (high) and native_templow (low).

    This function handles these scenarios:
    1. Normal day+night pair → combines into one entry
    2. Starts with night period (e.g., "Tonight") → standalone entry
    3. Day period without following night → standalone entry
    4. Consecutive night periods → each becomes standalone

    Returns a list of dicts matching HA's Forecast TypedDict shape.
    """
    daily = []
    i = 0

    while i < len(periods):
        period = periods[i]
        is_day = period.get("isDaytime", True)

        entry = {
            "datetime": period.get("startTime", ""),
            "condition": map_nws_condition(
                period.get("shortForecast", ""), is_day
            ),
            "precipitation_probability": extract_precip_probability(
                period.get("probabilityOfPrecipitation", {})
            ),
            "native_wind_speed": parse_wind_speed_text(
                period.get("windSpeed", "")
            ),
            "wind_bearing": period.get("windDirection") or None,
        }

        temp = period.get("temperature")

        if is_day:
            # Daytime period → this is the high
            entry["native_temperature"] = temp
            # Check if next period is the matching night
            if (
                i + 1 < len(periods)
                and not periods[i + 1].get("isDaytime", True)
            ):
                night = periods[i + 1]
                entry["native_templow"] = night.get("temperature")
                i += 2
            else:
                # No matching night — leave templow absent
                entry["native_templow"] = None
                i += 1
        else:
            # Night-only period (e.g., first period is "Tonight")
            # Use the night temp as both — HA needs native_temperature
            entry["native_temperature"] = temp
            entry["native_templow"] = temp
            i += 1

        daily.append(entry)

    return daily


def build_hourly_forecasts(periods: list[dict], limit: int = 48) -> list[dict]:
    """Convert NWS hourly forecast periods to HA Forecast format.

    Each hourly period is a standalone entry. Handles:
    - Mixed units (dewpoint in °C, temp in °F)
    - Null precipitation = 0%
    - Nested {value, unitCode} objects for dewpoint/humidity
    """
    hourly = []

    for period in periods[:limit]:
        is_day = period.get("isDaytime", True)

        entry = {
            "datetime": period.get("startTime", ""),
            "native_temperature": period.get("temperature"),
            "condition": map_nws_condition(
                period.get("shortForecast", ""), is_day
            ),
            "precipitation_probability": extract_precip_probability(
                period.get("probabilityOfPrecipitation", {})
            ),
            "native_wind_speed": parse_wind_speed_text(
                period.get("windSpeed", "")
            ),
            "wind_bearing": period.get("windDirection") or None,
        }

        # Dewpoint — may be nested {value, unitCode} in °C
        dewpoint_obj = period.get("dewpoint", {})
        if isinstance(dewpoint_obj, dict):
            dew_val = dewpoint_obj.get("value")
            dew_unit = dewpoint_obj.get("unitCode", "")
            if dew_val is not None:
                entry["native_dew_point"] = to_fahrenheit(dew_val, dew_unit)

        # Humidity — nested {value, unitCode}
        humidity_obj = period.get("relativeHumidity", {})
        if isinstance(humidity_obj, dict):
            hum_val = humidity_obj.get("value")
            if hum_val is not None:
                entry["humidity"] = round(hum_val, 1)

        hourly.append(entry)

    return hourly


def to_fahrenheit(value: float, unit_code: str) -> float | None:
    """Convert a temperature value to Fahrenheit based on its unit code."""
    if value is None:
        return None
    if "degC" in unit_code or "celsius" in unit_code.lower():
        return round(value * 9 / 5 + 32, 1)
    return round(value, 1)
