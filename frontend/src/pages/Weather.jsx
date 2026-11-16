import { useCallback, useEffect, useState } from "react";
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CloudRain, CloudSun, Droplets, LocateFixed, MapPin, Search, Sunrise, Sunset, Thermometer, Wind } from "lucide-react";
import { errorMessage } from "../api/client";
import { weather } from "../api/endpoints";
import { Card, EmptyState, ErrorBanner, PageHeader, PageLoader, Spinner } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { kmh } from "../utils/format";
import { getCurrentLocation } from "../utils/location";

const time = (iso) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
const day = (iso) => new Date(iso).toLocaleDateString([], { weekday: "short", day: "numeric" });

export default function Weather() {
  const { user } = useAuth();
  const saved = user.latitude != null
    ? { lat: user.latitude, lon: user.longitude, name: user.village || user.district, source: "saved" }
    : null;
  const [coords, setCoords] = useState(null);
  const [locating, setLocating] = useState(true);
  const [locNote, setLocNote] = useState(null);

  // Current position first (the farmer may be away from the farm); the saved farm location is the backup
  const locateMe = useCallback(async (fresh = false) => {
    setLocating(true);
    setLocNote(null);
    const here = await getCurrentLocation({ fresh });
    if (here) {
      setCoords({ ...here, name: null, source: "current" });
    } else {
      setLocNote("Could not get your current location (permission off?). Showing your saved farm location.");
      setCoords((c) => c || saved);
    }
    setLocating(false);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    locateMe();
  }, [locateMe]);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);

  const load = useCallback(() => {
    if (!coords) return;
    setData(null);
    setError(null);
    const params = { lat: coords.lat, lon: coords.lon };
    Promise.all([weather.current(params), weather.forecast(params)])
      .then(([current, forecast]) => setData({ current, forecast }))
      .catch((e) => setError(errorMessage(e)));
  }, [coords]);
  useEffect(load, [load]);

  const search = async (e) => {
    e.preventDefault();
    if (query.trim().length < 2) return;
    setSearching(true);
    try {
      setResults(await weather.geocode(query.trim()));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSearching(false);
    }
  };

  const chartData = data?.forecast.points.map((p) => ({
    t: `${day(p.time)} ${time(p.time)}`,
    temp: Math.round(p.temperature_c * 10) / 10,
    rain: p.rain_3h_mm,
    pop: Math.round(p.pop * 100),
  }));

  return (
    <div>
      <PageHeader title="Weather" subtitle="Live conditions, 5-day forecast and farm advice from OpenWeather." />
      <Card>
        <form className="search-row" onSubmit={search}>
          <input className="input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search a village, town or city" />
          <button className="btn btn-ghost" disabled={searching}>
            {searching ? <Spinner label="" size={16} /> : <Search size={18} />} Search
          </button>
        </form>
        <div className="location-row">
          <button type="button" className="btn btn-ghost" onClick={() => locateMe(true)} disabled={locating}>
            {locating ? <Spinner label="" size={16} /> : <LocateFixed size={18} />} Use my current location
          </button>
          {saved && coords?.source !== "saved" && (
            <button type="button" className="link-btn" onClick={() => setCoords(saved)}>
              <MapPin size={14} /> Saved farm location
            </button>
          )}
          {coords && (
            <span className="muted small">
              Showing: {coords.source === "current" ? "your current location" : coords.source === "saved" ? "saved farm location" : coords.name}
            </span>
          )}
        </div>
        {locNote && <p className="muted small">{locNote}</p>}
        {results.length > 0 && (
          <ul className="geo-results">
            {results.map((r) => (
              <li key={`${r.latitude},${r.longitude}`}>
                <button
                  className="link-btn"
                  onClick={() => {
                    setCoords({ lat: r.latitude, lon: r.longitude, name: r.name, source: "search" });
                    setResults([]);
                  }}
                >
                  <MapPin size={14} /> {r.name}
                  {r.state ? `, ${r.state}` : ""} ({r.country})
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {!coords && !locating && (
        <EmptyState icon={MapPin} title="No location yet">
          Search for your village above, or save your farm location on the Profile page.
        </EmptyState>
      )}
      <ErrorBanner message={error} onRetry={load} />
      {(locating && !coords) && <PageLoader label="Finding your location…" />}
      {coords && !data && !error && <PageLoader label="Fetching weather…" />}

      {data && (
        <>
          <div className="grid-2 mt">
            <Card title={(coords.source === "current" ? data.current.location_name : coords.name) || data.current.location_name || "Current weather"} icon={CloudSun}>
              <div className="weather-now big">
                <div className="weather-temp">{Math.round(data.current.temperature_c)}°C</div>
                <div className="capitalize">{data.current.description}</div>
              </div>
              <div className="weather-grid">
                <span><Thermometer size={16} /> Feels {Math.round(data.current.feels_like_c)}°C</span>
                <span><Droplets size={16} /> Humidity {data.current.humidity_pct}%</span>
                <span><Wind size={16} /> Wind {kmh(data.current.wind_speed_ms)} km/h</span>
                <span><CloudRain size={16} /> Rain (1 h) {data.current.rain_1h_mm ?? 0} mm</span>
                {data.current.sunrise && <span><Sunrise size={16} /> {time(data.current.sunrise)}</span>}
                {data.current.sunset && <span><Sunset size={16} /> {time(data.current.sunset)}</span>}
              </div>
              <p className="muted small">
                Updated {time(data.current.observed_at)}
                {data.current.cached ? " (cached)" : ""}
              </p>
            </Card>
            <Card title="Farm advice" icon={CloudSun}>
              {data.forecast.advisories.length ? (
                <ul className="advisory-list">
                  {data.forecast.advisories.map((a) => (
                    <li key={a.title} className={`advisory advisory-${a.level}`}>
                      <strong>{a.title}</strong>
                      <span>{a.message}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">No special weather risks in the next days.</p>
              )}
            </Card>
          </div>

          <Card title="Next 5 days" className="mt">
            <div className="day-strip">
              {data.forecast.daily.map((d) => (
                <div key={d.date} className="day">
                  <div className="day-name">{new Date(d.date).toLocaleDateString([], { weekday: "short", day: "numeric" })}</div>
                  <div className="day-temp">
                    {Math.round(d.temp_max_c)}° <span className="muted">{Math.round(d.temp_min_c)}°</span>
                  </div>
                  <div className="small"><CloudRain size={12} /> {d.rain_mm} mm · {Math.round(d.max_pop * 100)}%</div>
                </div>
              ))}
            </div>
            <div className="chart">
              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                  <XAxis dataKey="t" tick={{ fontSize: 11 }} interval={7} />
                  <YAxis yAxisId="temp" tick={{ fontSize: 11 }} unit="°" width={40} />
                  <YAxis yAxisId="rain" orientation="right" tick={{ fontSize: 11 }} unit=" mm" width={50} />
                  <Tooltip />
                  <Legend />
                  <Bar yAxisId="rain" dataKey="rain" name="Rain (3 h, mm)" fill="#5b9bd5" />
                  <Line yAxisId="temp" dataKey="temp" name="Temperature (°C)" stroke="#d9822b" dot={false} strokeWidth={2} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
