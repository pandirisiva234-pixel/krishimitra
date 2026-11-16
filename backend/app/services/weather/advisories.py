"""Rule-based farm advisories from weather data.

These are general agronomic rules of thumb (spray drift above ~15 km/h wind,
fungal risk in warm humid conditions, postponing fertilizer before heavy rain,
heat stress above 35 °C). Thresholds are constants so they can be cited and tuned
in the report. They are advisory, not a substitute for local extension advice.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

WIND_SPRAY_LIMIT_MS = 4.2  # ~15 km/h
HEAT_C = 35.0
COLD_C = 10.0
FUNGAL_HUMIDITY = 85
FUNGAL_TEMP_RANGE = (18.0, 30.0)
RAIN_POP = 0.6
HEAVY_RAIN_MM_24H = 10.0
DRY_SPELL_DAYS = 4
HEAVY_RAIN_DAY_MM = 20.0  # a day with this much rain later in the week deserves a heads-up


def daily_summaries(points: list[dict], tz_offset_sec: int = 0) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    tz = timezone(timedelta(seconds=tz_offset_sec))
    for p in points:
        t = p["time"] if isinstance(p["time"], datetime) else datetime.fromisoformat(p["time"])
        groups[t.astimezone(tz).date().isoformat()].append(p)
    days = []
    for day, items in sorted(groups.items()):
        temps = [i["temperature_c"] for i in items]
        days.append({
            "date": day,
            "temp_min_c": round(min(temps), 1),
            "temp_max_c": round(max(temps), 1),
            "rain_mm": round(sum(i["rain_3h_mm"] for i in items), 1),
            "max_pop": round(max(i["pop"] for i in items), 2),
            "avg_humidity_pct": round(sum(i["humidity_pct"] for i in items) / len(items), 1),
            "max_wind_ms": round(max(i["wind_speed_ms"] for i in items), 1),
        })
    return days


def build_advisories(current: dict | None, points: list[dict]) -> list[dict]:
    adv: list[dict] = []
    next24 = points[:8]  # 8 x 3-hour steps
    rain_24h = sum(p["rain_3h_mm"] for p in next24)
    max_pop_24h = max((p["pop"] for p in next24), default=0.0)
    max_temp_48h = max((p["temperature_c"] for p in points[:16]), default=None)
    min_temp_48h = min((p["temperature_c"] for p in points[:16]), default=None)
    wind_now = current["wind_speed_ms"] if current else (next24[0]["wind_speed_ms"] if next24 else 0.0)
    hum_now = current["humidity_pct"] if current else (next24[0]["humidity_pct"] if next24 else 0)
    temp_now = current["temperature_c"] if current else (next24[0]["temperature_c"] if next24 else None)

    if rain_24h >= HEAVY_RAIN_MM_24H or max_pop_24h >= RAIN_POP:
        adv.append({
            "level": "warning", "category": "rain",
            "title": "Rain expected in the next 24 hours",
            "message": f"About {rain_24h:.0f} mm forecast (chance up to {max_pop_24h:.0%}). Postpone fertilizer "
                       "and pesticide application, and clear field drains to avoid waterlogging.",
        })
    if wind_now > WIND_SPRAY_LIMIT_MS:
        adv.append({
            "level": "warning", "category": "spraying",
            "title": "Too windy to spray",
            "message": f"Wind is {wind_now * 3.6:.0f} km/h. Spray drift is likely above 15 km/h; spray in calm "
                       "early-morning or evening hours instead.",
        })
    elif max_pop_24h < 0.3 and wind_now <= WIND_SPRAY_LIMIT_MS:
        adv.append({
            "level": "info", "category": "spraying",
            "title": "Good conditions for spraying",
            "message": "Low wind and low rain chance. If spraying is needed, do it in the early morning or evening.",
        })
    if temp_now is not None and FUNGAL_TEMP_RANGE[0] <= temp_now <= FUNGAL_TEMP_RANGE[1] and hum_now >= FUNGAL_HUMIDITY:
        adv.append({
            "level": "warning", "category": "disease_risk",
            "title": "High risk of fungal diseases",
            "message": f"Humidity {hum_now}% with {temp_now:.0f} °C favours blights, mildews and leaf spots. "
                       "Inspect leaves closely and improve air flow between plants.",
        })
    if max_temp_48h is not None and max_temp_48h >= HEAT_C:
        adv.append({
            "level": "alert", "category": "heat",
            "title": "Heat stress likely",
            "message": f"Up to {max_temp_48h:.0f} °C in the next 2 days. Irrigate in the early morning or evening, "
                       "use mulch to keep soil moisture, and avoid spraying at midday.",
        })
    if min_temp_48h is not None and min_temp_48h <= COLD_C:
        adv.append({
            "level": "warning", "category": "cold",
            "title": "Cold night expected",
            "message": f"Down to {min_temp_48h:.0f} °C. Protect nurseries and young plants; light irrigation in the "
                       "evening reduces cold injury.",
        })
    days = daily_summaries(points)
    dry_days = sum(1 for d in days if d["rain_mm"] < 1 and d["max_pop"] < 0.3)
    if days and dry_days >= DRY_SPELL_DAYS and (max_temp_48h or 0) >= 30:
        adv.append({
            "level": "info", "category": "irrigation",
            "title": "Dry spell ahead",
            "message": f"No meaningful rain for {dry_days} days. Plan irrigation, preferably drip or furrow at "
                       "critical crop stages.",
        })
    later = [d for d in days[1:] if d["rain_mm"] >= HEAVY_RAIN_DAY_MM]
    if later:
        d = max(later, key=lambda x: x["rain_mm"])
        day = datetime.fromisoformat(d["date"]).strftime("%A")
        adv.append({
            "level": "warning", "category": "planning",
            "title": f"Heavy rain expected on {day}",
            "message": f"About {d['rain_mm']:.0f} mm forecast. Finish spraying, fertilizer and harvesting before "
                       "then, and clear field drains to avoid waterlogging.",
        })
    return adv


def weather_summary_text(current: dict | None, days: list[dict], advisories: list[dict]) -> str:
    lines = []
    if current:
        lines.append(
            f"Now at {current.get('location_name') or 'the farm'}: {current['temperature_c']:.0f} °C, "
            f"humidity {current['humidity_pct']}%, wind {current['wind_speed_ms'] * 3.6:.0f} km/h, {current['description']}."
        )
    for d in days[:5]:
        lines.append(
            f"{d['date']}: {d['temp_min_c']:.0f}-{d['temp_max_c']:.0f} °C, rain {d['rain_mm']} mm, "
            f"rain chance up to {d['max_pop']:.0%}."
        )
    for a in advisories:
        lines.append(f"Advisory ({a['category']}): {a['title']}. {a['message']}")
    return "\n".join(lines)
