"""
Helpers for parsing cached forecast JSON and computing rain risk.
Supports Open-Meteo daily (precipitation_sum, weathercode) and optional precip prob keys.
"""
import json
import urllib.request
import urllib.parse
from decimal import Decimal
from django.utils import timezone

RISK_HIGH = 'HIGH'
RISK_MODERATE = 'MODERATE'
RISK_LOW = 'LOW'
RISK_CLEAR = 'CLEAR'
RISK_UNKNOWN = 'UNKNOWN'

# WMO weather codes that imply rain (61,63,65=rain 80,81,82=showers 95,96,99=thunderstorm)
RAIN_WEATHERCODES = {61, 63, 65, 80, 81, 82, 95, 96, 99}


def get_daily_precip_prob(forecast_json, day_index):
    """
    Return 0-100 (int) precip probability for day at index, or None if unavailable.
    Tries: precipitation_probability_max, precipitation_probability, precip_prob, pop;
    else derives from precipitation_sum (mm) or weathercode.
    """
    if not forecast_json:
        return None
    try:
        data = json.loads(forecast_json) if isinstance(forecast_json, str) else forecast_json
    except (json.JSONDecodeError, TypeError):
        return None
    daily = data.get('daily') or {}
    if day_index < 0:
        return None
    # Explicit prob keys (Open-Meteo can return precipitation_probability_max)
    for key in ('precipitation_probability_max', 'precipitation_probability', 'precip_prob', 'pop'):
        arr = daily.get(key)
        if isinstance(arr, list) and day_index < len(arr):
            val = arr[day_index]
            if val is not None:
                try:
                    return min(100, max(0, int(float(val))))
                except (TypeError, ValueError):
                    pass
    # Derive from precipitation_sum (mm): rough mapping to %
    precips = daily.get('precipitation_sum') or []
    if day_index < len(precips):
        try:
            mm = float(precips[day_index])
            if mm >= 10:
                return 85
            if mm >= 5:
                return 60
            if mm >= 2:
                return 40
            if mm >= 0.5:
                return 20
            return 0
        except (TypeError, ValueError):
            pass
    # Weathercode: if rain code, treat as 60%
    codes = daily.get('weathercode') or []
    if day_index < len(codes):
        try:
            if int(codes[day_index]) in RAIN_WEATHERCODES:
                return 60
        except (TypeError, ValueError):
            pass
    return None


def get_max_precip_prob_7day(forecast_json):
    """Return max daily precipitation probability (0-100) across 7-day forecast, or None."""
    if not forecast_json:
        return None
    try:
        data = json.loads(forecast_json) if isinstance(forecast_json, str) else forecast_json
    except (json.JSONDecodeError, TypeError):
        return None
    times = (data.get('daily') or {}).get('time') or []
    if not times:
        return None
    max_prob = None
    for i in range(min(7, len(times))):
        p = get_daily_precip_prob(forecast_json, i)
        if p is not None:
            max_prob = p if max_prob is None else max(max_prob, p)
    return max_prob


def get_risk_level(forecast_json):
    """
    Use MAX daily precip prob across 7-day forecast.
    HIGH: >= 50%; MODERATE: 30-49%; LOW: 10-29%; CLEAR: < 10%.
    UNKNOWN only when forecast missing/failed.
    """
    max_prob = get_max_precip_prob_7day(forecast_json)
    if max_prob is None:
        return RISK_UNKNOWN
    if max_prob >= 50:
        return RISK_HIGH
    if max_prob >= 30:
        return RISK_MODERATE
    if max_prob >= 10:
        return RISK_LOW
    return RISK_CLEAR


def parse_forecast_days(forecast_json):
    """Return list of dicts: date, temp_max, temp_min, precip, precip_prob, wind (if present)."""
    if not forecast_json:
        return []
    try:
        data = json.loads(forecast_json) if isinstance(forecast_json, str) else forecast_json
    except (json.JSONDecodeError, TypeError):
        return []
    daily = data.get('daily') or {}
    times = daily.get('time') or []
    result = []
    for i, t in enumerate(times):
        highs = daily.get('temperature_2m_max') or []
        lows = daily.get('temperature_2m_min') or []
        precips = daily.get('precipitation_sum') or []
        winds = daily.get('windspeed_10m_max') or []
        day = {
            'date': t,
            'temp_max': highs[i] if i < len(highs) else None,
            'temp_min': lows[i] if i < len(lows) else None,
            'precip': precips[i] if i < len(precips) else None,
            'precip_prob': get_daily_precip_prob(forecast_json, i),
            'wind': winds[i] if i < len(winds) else None,
        }
        result.append(day)
    return result


def _project_has_address(project):
    return bool((getattr(project, 'city', None) or '').strip() or (getattr(project, 'state', None) or '').strip())


def get_forecast_for_project(project, force_refresh=False):
    """
    Return structured forecast for project or None.
    Uses Open-Meteo; caches in ProjectWeatherCache with 6h TTL unless force_refresh=True.
    Return shape: { "city", "state", "lat", "lon", "daily": [ {"date", "temp_max", "temp_min", "precip_prob", "weather_code"?} ] } or None.
    """
    from core.models import ProjectWeatherCache, ProjectWeatherLocation

    if not _project_has_address(project):
        return None
    city = (getattr(project, 'city', None) or '').strip()
    state = (getattr(project, 'state', None) or '').strip()

    cache = ProjectWeatherCache.objects.filter(project=project).first()
    location = ProjectWeatherLocation.objects.filter(project=project).first()
    now = timezone.now()
    # 15 min cache to avoid rate limits while keeping data fresh
    cache_ttl_seconds = 15 * 60

    if not force_refresh and cache and cache.fetched_at and cache.forecast_json:
        if (now - cache.fetched_at).total_seconds() < cache_ttl_seconds:
            daily = parse_forecast_days(cache.forecast_json)
            return {
                'city': city,
                'state': state,
                'lat': float(location.lat) if location else None,
                'lon': float(location.lon) if location else None,
                'daily': daily,
            }

    query = f"{city}, {state}".strip(', ')
    if not query:
        return None
    # Try "City, CA" and "City, California" for better geocode results
    queries_to_try = [query]
    if state.upper() == 'CA' and query:
        queries_to_try.append(f"{city}, California".strip(', '))
    lat, lon = None, None
    for q in queries_to_try:
        url = 'https://geocoding-api.open-meteo.com/v1/search?' + urllib.parse.urlencode({'name': q, 'count': 1})
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.loads(r.read().decode())
                results = data.get('results') or []
                if results:
                    lat = float(results[0]['latitude'])
                    lon = float(results[0]['longitude'])
                    break
        except Exception:
            continue
    if lat is None or lon is None:
        return None

    forecast_url = (
        'https://api.open-meteo.com/v1/forecast?'
        + urllib.parse.urlencode({
            'latitude': lat,
            'longitude': lon,
            'daily': 'precipitation_probability_max,temperature_2m_max,temperature_2m_min,weathercode',
            'timezone': 'America/Los_Angeles',
            'forecast_days': 7,
        })
    )
    try:
        with urllib.request.urlopen(forecast_url, timeout=10) as r:
            forecast = json.loads(r.read().decode())
    except Exception:
        return None

    ProjectWeatherLocation.objects.update_or_create(
        project=project,
        defaults={'lat': Decimal(str(lat)), 'lon': Decimal(str(lon)), 'geocode_source': 'open-meteo'}
    )
    ProjectWeatherCache.objects.update_or_create(
        project=project,
        defaults={'forecast_json': json.dumps(forecast), 'fetched_at': now}
    )
    daily = parse_forecast_days(json.dumps(forecast))
    return {
        'city': city,
        'state': state,
        'lat': lat,
        'lon': lon,
        'daily': daily,
    }
