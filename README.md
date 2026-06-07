# NWS Weather Forecast

[![Validate](https://github.com/seyme/ha-nws-forecast/actions/workflows/validate.yml/badge.svg)](https://github.com/seyme/ha-nws-forecast/actions/workflows/validate.yml)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration that provides weather data from the [U.S. National Weather Service (NWS) API](https://www.weather.gov/documentation/services-web-api).

This integration is intended for **United States locations only**.

## Features

- Weather entity with current conditions from the nearest NWS observation station
- Daily forecast (paired day/night periods for Home Assistant weather cards)
- Hourly forecast (up to 48 hours)
- Setup via UI config flow using a 5-digit US zip code
- Polls NWS every hour (manual refresh also supported)

## Integration icon

Home Assistant looks for the integration icon at:

```text
custom_components/nws_forecast/brand/icon.png
```

Use a **256×256 PNG**. If you see "icon not available" in HA, make sure that file exists on your instance (not just at the integration root).

## Installation

### HACS (recommended)

1. Open **HACS → Integrations → Explore & Download Repositories** (or add as a custom repository).
2. Add this repository as a custom repository if it is not in the default store yet:
   - Repository URL: `https://github.com/seyme/ha-nws-forecast`
   - Category: **Integration**
3. Search for **NWS Weather Forecast** and install it.
4. Restart Home Assistant.
5. Go to **Settings → Devices & Services → Add Integration** and search for **NWS Weather Forecast**.

### Manual installation

1. Copy the `custom_components/nws_forecast` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Add the integration from **Settings → Devices & Services**.

## Configuration

During setup, enter a **5-digit US zip code**. The integration will:

1. Resolve the zip code to latitude/longitude
2. Look up the NWS forecast grid for that location
3. Create a weather entity for that location

Each zip code can only be configured once.

## Entities

| Entity | Description |
| --- | --- |
| `weather.nws_forecast_<zip>` | Weather entity with current conditions, daily forecast, and hourly forecast |

Example entity ID for zip code `80304`:

```text
weather.nws_forecast_80304
```

### Supported data

| Attribute | Source |
| --- | --- |
| Temperature, dew point, humidity | Nearest NWS observation station |
| Wind speed and direction | Observation (METAR fallback when needed) |
| Pressure, visibility, cloud cover | Observation |
| Daily forecast | NWS `/forecast` endpoint |
| Hourly forecast | NWS `/forecast/hourly` endpoint |

## Update interval

The integration polls NWS **once per hour** by default. You can trigger an immediate update with the `homeassistant.update_entity` service on the weather entity.

## API endpoints used

| When | Endpoint |
| --- | --- |
| Setup | `api.zippopotam.us` (zip → coordinates) |
| Setup | `api.weather.gov/points/{lat},{lon}` |
| Updates | `api.weather.gov/gridpoints/.../forecast` |
| Updates | `api.weather.gov/gridpoints/.../forecast/hourly` |
| Updates | `api.weather.gov/stations/{id}/observations/latest` |

NWS requires a descriptive User-Agent header; this integration identifies itself as `HomeAssistant-NWS-Forecast/1.0.0`.

## Development

Run the standalone mapping tests from the repository root:

```bash
python test_nws_mapping.py
python test_nws_mapping.py 80304
```

## Disclaimer

This is an unofficial integration. It is not affiliated with or endorsed by the National Weather Service or NOAA.

Data is provided by third-party APIs (NWS and zippopotam.us). Always consult official sources for safety-critical weather decisions.

## License

MIT — see [LICENSE](LICENSE).
