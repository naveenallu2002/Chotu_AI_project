import requests


def _to_int(value, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def _format_hour_label(raw_time: str, index: int) -> str:
    if index == 0:
        return "Now"

    hour = _to_int(raw_time) // 100
    if hour == 0:
        return "12 AM"
    if hour < 12:
        return f"{hour} AM"
    if hour == 12:
        return "12 PM"
    return f"{hour - 12} PM"


def _build_hourly_forecast(day_data: dict) -> list[dict]:
    items = []
    for index, entry in enumerate(day_data.get("hourly", [])[:5]):
        chance_of_rain = max(
            _to_int(entry.get("chanceofrain")),
            _to_int(entry.get("chanceofthunder")),
            _to_int(entry.get("chanceofsnow")),
        )
        items.append(
            {
                "time": _format_hour_label(entry.get("time"), index),
                "temp_c": _to_int(entry.get("tempC")),
                "condition": entry.get("weatherDesc", [{}])[0].get("value", "Clear"),
                "wind_kph": _to_int(entry.get("windspeedKmph")),
                "chance_of_rain": chance_of_rain,
            }
        )
    return items


def get_weather(city: str) -> dict:
    if not city:
        raise ValueError("Please provide a city name.")

    try:
        url = f"https://wttr.in/{city}?format=j1"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        current = data.get("current_condition", [{}])[0]
        today = data.get("weather", [{}])[0]
        resolved_city = city.strip().title()

        return {
            "city": resolved_city,
            "condition": current.get("weatherDesc", [{}])[0].get("value", "Clear"),
            "temperature_c": _to_int(current.get("temp_C")),
            "feels_like_c": _to_int(current.get("FeelsLikeC")),
            "min_temp_c": _to_int(today.get("mintempC")),
            "max_temp_c": _to_int(today.get("maxtempC")),
            "humidity": _to_int(current.get("humidity")),
            "wind_kph": _to_int(current.get("windspeedKmph")),
            "wind_text": f"Force {_to_int(current.get('windspeedKmph')) // 12 + 1}",
            "moon_phase": today.get("astronomy", [{}])[0].get("moon_phase", "Waxing Crescent"),
            "is_day": str(current.get("isdaytime", "yes")).lower() == "yes",
            "hourly": _build_hourly_forecast(today),
        }
    except Exception as e:
        raise RuntimeError(f"Could not fetch weather for {city}. Error: {str(e)}") from e
