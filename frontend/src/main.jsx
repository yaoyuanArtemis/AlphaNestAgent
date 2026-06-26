import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API_URL = "http://127.0.0.1:8000";

const MACRO_INDICATORS = [
  {
    value: "CPI",
    label: "CPI",
    description: "Consumer price index trend for inflation pressure.",
    cadence: "Monthly",
    source: "Alpha Vantage",
    tags: ["Inflation", "Prices"],
  },
  {
    value: "FEDERAL_FUNDS_RATE",
    label: "Federal Funds Rate",
    description: "Policy rate backdrop for liquidity and valuation risk.",
    cadence: "Monthly",
    source: "Alpha Vantage",
    tags: ["Fed", "Rates"],
  },
  {
    value: "UNEMPLOYMENT",
    label: "Unemployment",
    description: "Labor market slack and recession-cycle signal.",
    cadence: "Monthly",
    source: "Alpha Vantage",
    tags: ["Labor", "Cycle"],
  },
  {
    value: "NONFARM_PAYROLL",
    label: "Nonfarm Payroll",
    description: "Employment growth momentum for US macro demand.",
    cadence: "Monthly",
    source: "Alpha Vantage",
    tags: ["Jobs", "Macro"],
  },
  {
    value: "INFLATION",
    label: "Inflation",
    description: "Annual inflation series for long-range price trend.",
    cadence: "Annual",
    source: "Alpha Vantage",
    tags: ["Inflation", "Annual"],
  },
  {
    value: "RETAIL_SALES",
    label: "Retail Sales",
    description: "Consumer spending pulse across the US economy.",
    cadence: "Monthly",
    source: "Alpha Vantage",
    tags: ["Consumer", "Demand"],
  },
  {
    value: "QUADRUPLE_WITCHING",
    label: "Quadruple Witching",
    description: "Future quarterly expiration dates marked on calendars.",
    cadence: "Quarterly",
    source: "Calendar rule",
    tags: ["Options", "Expiry"],
  },
];

const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const QUADRUPLE_WITCHING_MONTHS = [2, 5, 8, 11];
const MACRO_INDICATOR_BY_SLUG = new Map(
  MACRO_INDICATORS.map((item) => [item.value.toLowerCase().replaceAll("_", "-"), item.value]),
);

function getIndicatorSlug(value) {
  return value.toLowerCase().replaceAll("_", "-");
}

function readRouteFromLocation() {
  const route = window.location.hash.replace(/^#\/?/, "");
  const [section, slug] = route.split("/");

  if (section === "chat") {
    return { activeTab: "chat", indicator: null };
  }

  if (section === "macro") {
    return {
      activeTab: "macro",
      indicator: MACRO_INDICATOR_BY_SLUG.get(slug) ?? null,
    };
  }

  return { activeTab: "macro", indicator: null };
}

function getRouteHash(route) {
  if (route.activeTab === "chat") {
    return "#/chat";
  }

  if (route.indicator) {
    return `#/macro/${getIndicatorSlug(route.indicator)}`;
  }

  return "#/macro";
}

function writeRouteToLocation(route, replace = false) {
  const nextHash = getRouteHash(route);
  if (window.location.hash === nextHash) {
    return;
  }

  window.history[replace ? "replaceState" : "pushState"]({}, "", nextHash);
}

function formatDateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatReadableDate(date) {
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function getThirdFriday(year, monthIndex) {
  const firstDay = new Date(year, monthIndex, 1);
  const firstFridayOffset = (5 - firstDay.getDay() + 7) % 7;
  return new Date(year, monthIndex, 1 + firstFridayOffset + 14);
}

function getFutureQuadrupleWitchingDates(count = 8) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const events = [];
  let year = today.getFullYear();

  while (events.length < count) {
    QUADRUPLE_WITCHING_MONTHS.forEach((monthIndex) => {
      const date = getThirdFriday(year, monthIndex);
      if (date >= today) {
        events.push({
          date,
          key: formatDateKey(date),
          quarter: `Q${Math.floor(monthIndex / 3) + 1}`,
        });
      }
    });
    year += 1;
  }

  return events.slice(0, count);
}

function buildCalendarMonth(event) {
  const year = event.date.getFullYear();
  const month = event.date.getMonth();
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const days = [];

  for (let index = 0; index < firstDay.getDay(); index += 1) {
    days.push(null);
  }

  for (let day = 1; day <= lastDay.getDate(); day += 1) {
    const date = new Date(year, month, day);
    days.push({
      day,
      key: formatDateKey(date),
      isEvent: formatDateKey(date) === event.key,
    });
  }

  return {
    ...event,
    monthLabel: event.date.toLocaleDateString(undefined, {
      year: "numeric",
      month: "long",
    }),
    days,
  };
}

function createSessionId() {
  if (crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function App() {
  const [route, setRoute] = useState(() => readRouteFromLocation());
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Ask me about US stocks, recent price action, or market opportunities. I can fetch historical prices when needed.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const sessionIdRef = useRef(createSessionId());
  const canSend = useMemo(() => input.trim().length > 0 && !isLoading, [input, isLoading]);
  const activeTab = route.activeTab;

  useEffect(() => {
    if (!window.location.hash) {
      writeRouteToLocation(route, true);
    }

    function syncRouteFromLocation() {
      setRoute(readRouteFromLocation());
    }

    window.addEventListener("popstate", syncRouteFromLocation);
    window.addEventListener("hashchange", syncRouteFromLocation);

    return () => {
      window.removeEventListener("popstate", syncRouteFromLocation);
      window.removeEventListener("hashchange", syncRouteFromLocation);
    };
  }, []);

  function navigate(nextRoute) {
    setRoute(nextRoute);
    writeRouteToLocation(nextRoute);
  }

  async function sendMessage(event) {
    event.preventDefault();
    if (!canSend) return;

    const userMessage = input.trim();
    setInput("");
    setIsLoading(true);
    setMessages((current) => [...current, { role: "user", content: userMessage }]);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          message: userMessage,
        }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(JSON.stringify(payload.error ?? payload, null, 2));
      }

      sessionIdRef.current = payload.session_id;
      setMessages((current) => [...current, { role: "assistant", content: payload.reply }]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: `Request failed:\n${error.message}`,
          isError: true,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  async function resetChat() {
    await fetch(`${API_URL}/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionIdRef.current }),
    }).catch(() => {});

    sessionIdRef.current = createSessionId();
    setMessages([
      {
        role: "assistant",
        content:
          "Session reset. Ask me about a ticker such as RKLB, NVDA, AAPL, or a broader US market setup.",
      },
    ]);
  }

  return (
    <main className="app-shell">
      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>AlphaNestAgent</h1>
            <p>US stock research assistant</p>
          </div>
          <div className="topbar-actions">
            <nav className="tabs" aria-label="Primary views">
              <button
                className={activeTab === "macro" ? "tab tab-active" : "tab"}
                type="button"
                onClick={() => navigate({ activeTab: "macro", indicator: null })}
              >
                Macro
              </button>
              <button
                className={activeTab === "chat" ? "tab tab-active" : "tab"}
                type="button"
                onClick={() => navigate({ activeTab: "chat", indicator: null })}
              >
                Chat
              </button>
            </nav>
            {activeTab === "chat" && (
              <button className="secondary-button" type="button" onClick={resetChat}>
                Reset
              </button>
            )}
          </div>
        </header>

        {activeTab === "chat" ? (
          <>
            <div className="messages" aria-live="polite">
              {messages.map((message, index) => (
                <article
                  className={`message ${message.role === "user" ? "message-user" : "message-agent"} ${
                    message.isError ? "message-error" : ""
                  }`}
                  key={`${message.role}-${index}`}
                >
                  <div className="message-label">{message.role === "user" ? "You" : "AlphaNestAgent"}</div>
                  <div className="message-content">{message.content}</div>
                </article>
              ))}
              {isLoading && (
                <article className="message message-agent">
                  <div className="message-label">AlphaNestAgent</div>
                  <div className="message-content">Thinking...</div>
                </article>
              )}
            </div>

            <form className="composer" onSubmit={sendMessage}>
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Ask about RKLB, NVDA, earnings risk, or recent price action..."
                rows={3}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    sendMessage(event);
                  }
                }}
              />
              <button type="submit" disabled={!canSend}>
                Send
              </button>
            </form>
          </>
        ) : (
          <MacroPanel
            indicator={route.indicator}
            onSelectIndicator={(nextIndicator) =>
              navigate({ activeTab: "macro", indicator: nextIndicator })
            }
          />
        )}
      </section>
    </main>
  );
}

function MacroPanel({ indicator, onSelectIndicator }) {
  const [interval, setInterval] = useState("monthly");
  const [macroData, setMacroData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const hasSelectedIndicator = indicator !== null;
  const isQuadrupleWitching = indicator === "QUADRUPLE_WITCHING";
  const quadrupleWitchingEvents = useMemo(() => getFutureQuadrupleWitchingDates(8), []);

  useEffect(() => {
    if (!hasSelectedIndicator) {
      setMacroData(null);
      setError("");
      setIsLoading(false);
      return;
    }

    if (isQuadrupleWitching) {
      setMacroData(null);
      setError("");
      setIsLoading(false);
      return;
    }

    loadMacroData();
  }, [indicator, interval]);

  async function loadMacroData() {
    if (!hasSelectedIndicator) {
      return;
    }

    if (isQuadrupleWitching) {
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const params = new URLSearchParams({
        indicator,
        interval,
        limit: "120",
      });
      const response = await fetch(`${API_URL}/macro?${params.toString()}`);
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(JSON.stringify(payload.error ?? payload, null, 2));
      }

      setMacroData(payload);
    } catch (requestError) {
      setMacroData(null);
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  }

  const rows = macroData?.data ?? [];
  const chartRows = useMemo(
    () =>
      rows
        .map((row) => ({
          date: row.date,
          value: Number(row.value),
        }))
        .filter((row) => Number.isFinite(row.value)),
    [rows],
  );
  const intervalDisabled = indicator === "INFLATION" || isQuadrupleWitching;
  const latestPoint = chartRows.at(-1);
  const selectedIndicator = MACRO_INDICATORS.find((item) => item.value === indicator);
  const selectedIndicatorLabel = selectedIndicator?.label ?? indicator;
  const nextWitchingEvent = quadrupleWitchingEvents[0];

  if (!hasSelectedIndicator) {
    return (
      <section className="macro-panel macro-panel-index">
        <IndicatorCardGrid onSelect={onSelectIndicator} />
      </section>
    );
  }

  return (
    <section className="macro-panel">
      <div className="macro-toolbar">
        <label>
          <span>Interval</span>
          <select
            value={interval}
            disabled={intervalDisabled}
            onChange={(event) => setInterval(event.target.value)}
          >
            <option value="monthly">Monthly</option>
            <option value="quarterly">Quarterly</option>
            <option value="annual">Annual</option>
          </select>
        </label>

        <div className="macro-toolbar-actions">
          <button className="secondary-button" type="button" onClick={() => onSelectIndicator(null)}>
            Back
          </button>
          <button className="secondary-button" type="button" onClick={loadMacroData} disabled={isQuadrupleWitching}>
            Refresh
          </button>
        </div>
      </div>

      <div className="macro-content">
        <div className="macro-summary">
          <div>
            <div className="summary-label">Source</div>
            <div className="summary-value">
              {isQuadrupleWitching ? "Calendar Rule" : macroData?.source ?? "Alpha Vantage"}
            </div>
          </div>
          <div>
            <div className="summary-label">{isQuadrupleWitching ? "Events Shown" : "Rows Shown"}</div>
            <div className="summary-value">
              {isQuadrupleWitching ? quadrupleWitchingEvents.length : chartRows.length}
            </div>
          </div>
          <div>
            <div className="summary-label">{isQuadrupleWitching ? "Next Date" : "Latest"}</div>
            <div className="summary-value">
              {isQuadrupleWitching
                ? nextWitchingEvent
                  ? formatReadableDate(nextWitchingEvent.date)
                  : "-"
                : latestPoint
                  ? `${latestPoint.value} (${latestPoint.date})`
                  : "-"}
            </div>
          </div>
        </div>

        {isLoading && <div className="state-box">Loading macro data...</div>}
        {error && <div className="state-box state-error">Request failed: {error}</div>}

        {!isLoading && !error && isQuadrupleWitching && (
          <QuadrupleWitchingCalendar events={quadrupleWitchingEvents} />
        )}

        {!isLoading && !error && !isQuadrupleWitching && (
          <MacroChart data={chartRows} title={selectedIndicatorLabel} />
        )}
      </div>
    </section>
  );
}

function IndicatorCardGrid({ selectedValue, onSelect }) {
  return (
    <div className="indicator-board">
      <div className="indicator-board-header">
        <span>Indicators</span>
        <strong>Macro watchlist</strong>
      </div>

      <div className="indicator-card-grid">
        {MACRO_INDICATORS.map((item) => {
          const isSelected = item.value === selectedValue;

          return (
            <button
              className={isSelected ? "indicator-card indicator-card-active" : "indicator-card"}
              key={item.value}
              type="button"
              onClick={() => onSelect(item.value)}
              aria-pressed={isSelected}
            >
              <div className="indicator-tags">
                {item.tags.map((tag) => (
                  <span className="indicator-tag" key={tag}>
                    {tag}
                  </span>
                ))}
              </div>

              <div className="indicator-card-body">
                <strong>{item.label}</strong>
                <p>{item.description}</p>
              </div>

              <div className="indicator-card-footer">
                <span>{item.cadence}</span>
                <span>{item.source}</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function QuadrupleWitchingCalendar({ events }) {
  const months = useMemo(() => events.map(buildCalendarMonth), [events]);

  return (
    <div className="witching-calendar">
      <div className="witching-calendar-header">
        <div>
          <div className="chart-title">Quadruple Witching Calendar</div>
          <div className="chart-subtitle">Third Friday of March, June, September, and December</div>
        </div>
        <div className="witching-badge">Future dates</div>
      </div>

      <div className="witching-month-grid">
        {months.map((month) => (
          <article className="witching-month" key={month.key}>
            <div className="witching-month-header">
              <div>
                <strong>{month.monthLabel}</strong>
                <span>{month.quarter}</span>
              </div>
              <div className="witching-date-pill">{formatReadableDate(month.date)}</div>
            </div>

            <div className="calendar-weekdays">
              {WEEKDAY_LABELS.map((day) => (
                <span key={day}>{day}</span>
              ))}
            </div>

            <div className="calendar-days">
              {month.days.map((day, index) =>
                day ? (
                  <div
                    className={day.isEvent ? "calendar-day calendar-day-event" : "calendar-day"}
                    key={day.key}
                    title={day.isEvent ? "Quadruple witching" : undefined}
                  >
                    <span>{day.day}</span>
                    {day.isEvent && <small>Witching</small>}
                  </div>
                ) : (
                  <div className="calendar-day calendar-day-empty" key={`empty-${month.key}-${index}`} />
                ),
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function MacroChart({ data, title }) {
  const [hoveredIndex, setHoveredIndex] = useState(null);
  const width = 920;
  const height = 420;
  const padding = { top: 34, right: 34, bottom: 58, left: 70 };

  const chart = useMemo(() => {
    if (data.length === 0) {
      return null;
    }

    const values = data.map((row) => row.value);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const range = maxValue - minValue || 1;
    const niceMin = minValue - range * 0.08;
    const niceMax = maxValue + range * 0.08;
    const niceRange = niceMax - niceMin || 1;
    const innerWidth = width - padding.left - padding.right;
    const innerHeight = height - padding.top - padding.bottom;

    const points = data.map((row, index) => {
      const x =
        padding.left + (data.length === 1 ? innerWidth / 2 : (index / (data.length - 1)) * innerWidth);
      const y = padding.top + (1 - (row.value - niceMin) / niceRange) * innerHeight;
      return { ...row, x, y };
    });

    const linePath = points
      .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
      .join(" ");
    const areaPath = `${linePath} L ${points.at(-1).x.toFixed(2)} ${height - padding.bottom} L ${points[0].x.toFixed(
      2,
    )} ${height - padding.bottom} Z`;

    const ticks = Array.from({ length: 5 }, (_, index) => {
      const ratio = index / 4;
      const value = niceMin + (1 - ratio) * niceRange;
      const y = padding.top + ratio * innerHeight;
      return { value, y };
    });

    const dateTicks = [0, Math.floor((data.length - 1) / 2), data.length - 1]
      .filter((index, position, indexes) => indexes.indexOf(index) === position)
      .map((index) => points[index]);

    return { areaPath, dateTicks, linePath, points, ticks };
  }, [data]);

  if (!chart) {
    return <div className="state-box">No macro data returned.</div>;
  }

  const hoveredPoint = hoveredIndex === null ? chart.points.at(-1) : chart.points[hoveredIndex];

  function handlePointerMove(event) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - bounds.left) / bounds.width) * width;
    const nearest = chart.points.reduce(
      (best, point, index) => {
        const distance = Math.abs(point.x - x);
        return distance < best.distance ? { distance, index } : best;
      },
      { distance: Number.POSITIVE_INFINITY, index: 0 },
    );
    setHoveredIndex(nearest.index);
  }

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div>
          <div className="chart-title">{title}</div>
          <div className="chart-subtitle">Historical macro indicator trend</div>
        </div>
        {hoveredPoint && (
          <div className="chart-readout">
            <span>{hoveredPoint.date}</span>
            <strong>{hoveredPoint.value}</strong>
          </div>
        )}
      </div>

      <svg
        className="macro-chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${title} line chart`}
        onPointerMove={handlePointerMove}
        onPointerLeave={() => setHoveredIndex(null)}
      >
        <defs>
          <linearGradient id="macroLineGradient" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="#245c6b" />
            <stop offset="52%" stopColor="#2f8c8f" />
            <stop offset="100%" stopColor="#7a8f2a" />
          </linearGradient>
          <linearGradient id="macroAreaGradient" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#2f8c8f" stopOpacity="0.32" />
            <stop offset="72%" stopColor="#2f8c8f" stopOpacity="0.06" />
            <stop offset="100%" stopColor="#2f8c8f" stopOpacity="0" />
          </linearGradient>
          <filter id="lineGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <rect
          className="plot-background"
          x={padding.left}
          y={padding.top}
          width={width - padding.left - padding.right}
          height={height - padding.top - padding.bottom}
          rx="12"
        />

        {chart.ticks.map((tick) => (
          <g key={tick.y}>
            <line className="grid-line" x1={padding.left} x2={width - padding.right} y1={tick.y} y2={tick.y} />
            <text className="axis-label" x={padding.left - 14} y={tick.y + 4} textAnchor="end">
              {tick.value.toFixed(2)}
            </text>
          </g>
        ))}

        {chart.dateTicks.map((tick) => (
          <text className="axis-label" x={tick.x} y={height - 22} textAnchor="middle" key={tick.date}>
            {tick.date}
          </text>
        ))}

        <path className="area-path" d={chart.areaPath} />
        <path className="line-path line-glow" d={chart.linePath} />
        <path className="line-path" d={chart.linePath} />

        {hoveredPoint && (
          <g>
            <line
              className="hover-line"
              x1={hoveredPoint.x}
              x2={hoveredPoint.x}
              y1={padding.top}
              y2={height - padding.bottom}
            />
            <circle className="hover-point-ring" cx={hoveredPoint.x} cy={hoveredPoint.y} r="8" />
            <circle className="hover-point" cx={hoveredPoint.x} cy={hoveredPoint.y} r="4.5" />
          </g>
        )}
      </svg>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
