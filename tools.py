from pathlib import Path
import csv
import json
import os
import socket
import time
from urllib.parse import urlencode
from urllib.request import urlopen


basePath = Path("")


def read_file(name:str) -> str:

    print(f"read_file{name}")
    try:
        with open(basePath / name,"r") as f:
            content = f.read()
        return content
    except Exception as e:
        return f"An error occured:{e}"


def list_files() -> list[str]:
    print("(list_file)")
    file_list = []
    for item in basePath.rglob("*"):
        if item.is_file():
            file_list.append(str(item.relative_to(basePath)))

    return file_list


def rename_name(name:str,new_name:str) -> str:
    print(f"rename_file{name} -> {new_name}")
    try:
        new_path = basePath / new_name
        if not str(new_path).startswith(str(basePath)):
            return "Error: new_name is outside basePath."

        os.makedirs(new_path.parent, exist_ok=True)
        os.rename(basePath / name, new_path)
        return f"File '{name}' successfully renamed to '{new_name}'."
    except Exception as e:
        return f"An error occurred: {e}"
    

import yfinance as yf
from yfinance.exceptions import YFRateLimitError
import pandas as pd


ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
_CACHE_TTL_SECONDS = 15 * 60
_api_cache: dict[tuple, tuple[float, dict | list]] = {}


def _get_alpha_vantage_key() -> str | None:
    return os.getenv("ALPHA_VANTAGE_API_KEY")


def _cached_get(cache_key: tuple) -> dict | list | None:
    cached = _api_cache.get(cache_key)
    if not cached:
        return None

    created_at, value = cached
    if time.time() - created_at > _CACHE_TTL_SECONDS:
        _api_cache.pop(cache_key, None)
        return None

    return value


def _cached_set(cache_key: tuple, value: dict | list) -> dict | list:
    _api_cache[cache_key] = (time.time(), value)
    return value


def _alpha_vantage_json(params: dict[str, str]) -> dict:
    api_key = _get_alpha_vantage_key()
    if not api_key:
        return {
            "error_type": "missing_api_key",
            "error": "ALPHA_VANTAGE_API_KEY is not set.",
        }

    request_params = {**params, "apikey": api_key}
    cache_key = ("json", tuple(sorted(request_params.items())))
    cached = _cached_get(cache_key)
    if isinstance(cached, dict):
        return cached

    url = f"{ALPHA_VANTAGE_URL}?{urlencode(request_params)}"
    try:
        with urlopen(url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        return {
            "error_type": type(error).__name__,
            "error": str(error),
        }

    if "Error Message" in payload:
        return {"error_type": "api_error", "error": payload["Error Message"]}
    if "Information" in payload:
        return {"error_type": "api_notice", "error": payload["Information"]}
    if "Note" in payload:
        return {"error_type": "rate_limited", "error": payload["Note"]}

    return _cached_set(cache_key, payload)


def _alpha_vantage_csv(params: dict[str, str]) -> list[dict[str, str]] | dict:
    api_key = _get_alpha_vantage_key()
    if not api_key:
        return {
            "error_type": "missing_api_key",
            "error": "ALPHA_VANTAGE_API_KEY is not set.",
        }

    request_params = {**params, "apikey": api_key}
    cache_key = ("csv", tuple(sorted(request_params.items())))
    cached = _cached_get(cache_key)
    if isinstance(cached, list):
        return cached

    url = f"{ALPHA_VANTAGE_URL}?{urlencode(request_params)}"
    try:
        with urlopen(url, timeout=20) as response:
            text = response.read().decode("utf-8")
    except Exception as error:
        return {
            "error_type": type(error).__name__,
            "error": str(error),
        }

    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"error": text}
        return {
            "error_type": "api_error",
            "error": payload.get("Information") or payload.get("Note") or payload.get("Error Message") or payload,
        }

    rows = list(csv.DictReader(text.splitlines()))
    return _cached_set(cache_key, rows)


def _format_alpha_vantage_daily(symbol: str, period: str, interval: str, payload: dict) -> dict:
    time_series = payload.get("Time Series (Daily)")
    if not isinstance(time_series, dict):
        return {
            "symbol": symbol.upper(),
            "period": period,
            "interval": interval,
            "source": "alpha_vantage",
            "error_type": "unexpected_response",
            "error": payload,
        }

    rows = []
    for date, values in sorted(time_series.items()):
        rows.append(
            {
                "Date": date,
                "Open": float(values["1. open"]),
                "High": float(values["2. high"]),
                "Low": float(values["3. low"]),
                "Close": float(values["4. close"]),
                "Volume": int(values["5. volume"]),
            }
        )

    recent = rows[-10:]
    return {
        "symbol": symbol.upper(),
        "period": period,
        "interval": interval,
        "source": "alpha_vantage",
        "rows": len(rows),
        "latest_close": recent[-1]["Close"] if recent else None,
        "recent_data": recent,
    }


def alpha_vantage_stock_history(symbol: str, period: str = "6mo", interval: str = "1d") -> dict:
    """Get daily stock history from Alpha Vantage.

    Args:
        symbol: Stock ticker symbol, for example AAPL, MSFT, NVDA.
        period: Kept for compatibility with yahoo_stock_history. Alpha Vantage free daily compact returns latest 100 bars.
        interval: Kept for compatibility. This function returns daily bars.
    """
    print(f"(alpha_vantage_stock_history {symbol})")
    payload = _alpha_vantage_json(
        {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol.upper(),
            "outputsize": "compact",
        }
    )

    if "error_type" in payload:
        return {
            "symbol": symbol.upper(),
            "period": period,
            "interval": interval,
            "source": "alpha_vantage",
            **payload,
        }

    return _format_alpha_vantage_daily(symbol, period, interval, payload)


def yahoo_stock_history(symbol: str, period: str = "6mo", interval: str = "1d") -> dict:
    """Get recent historical OHLCV data from Yahoo Finance, with Alpha Vantage fallback.

    Args:
        symbol: Stock ticker symbol, for example AAPL, MSFT, NVDA.
        period: Data period supported by yfinance, for example 1mo, 3mo, 6mo, 1y.
        interval: Data interval supported by yfinance, for example 1d, 1wk, 1mo.
    """
    print(f"(yahoo_stock_history {symbol}, period={period}, interval={interval})")
    ticker = yf.Ticker(symbol)
    try:
        history: pd.DataFrame = ticker.history(period=period, interval=interval)
    except YFRateLimitError as error:
        fallback = alpha_vantage_stock_history(symbol, period, interval)
        fallback["fallback_reason"] = f"Yahoo Finance rate-limited the request: {error}"
        return fallback
    except Exception as error:
        fallback = alpha_vantage_stock_history(symbol, period, interval)
        fallback["fallback_reason"] = f"Yahoo Finance failed with {type(error).__name__}: {error}"
        return fallback

    if history.empty:
        fallback = alpha_vantage_stock_history(symbol, period, interval)
        fallback["fallback_reason"] = "Yahoo Finance returned no historical data."
        return fallback

    recent = history.tail(10).reset_index()
    recent["Date"] = recent["Date"].astype(str)

    return {
        "symbol": symbol.upper(),
        "period": period,
        "interval": interval,
        "source": "yfinance",
        "rows": len(history),
        "latest_close": float(history["Close"].iloc[-1]),
        "recent_data": recent.to_dict(orient="records"),
    }



def company_overview(symbol: str) -> dict:
    """Get company profile and fundamental summary data from Alpha Vantage.

    Args:
        symbol: Stock ticker symbol, for example AAPL, MSFT, NVDA.
    """
    print(f"(company_overview {symbol})")
    payload = _alpha_vantage_json({"function": "OVERVIEW", "symbol": symbol.upper()})
    if "error_type" in payload:
        return {"symbol": symbol.upper(), "source": "alpha_vantage", **payload}
    if not payload:
        return {
            "symbol": symbol.upper(),
            "source": "alpha_vantage",
            "error_type": "empty_response",
            "error": "No company overview found.",
        }

    fields = [
        "Symbol",
        "Name",
        "Description",
        "Sector",
        "Industry",
        "MarketCapitalization",
        "PERatio",
        "PEGRatio",
        "EPS",
        "RevenueTTM",
        "ProfitMargin",
        "52WeekHigh",
        "52WeekLow",
        "AnalystTargetPrice",
    ]
    return {
        "symbol": symbol.upper(),
        "source": "alpha_vantage",
        "overview": {field: payload.get(field) for field in fields if payload.get(field) not in (None, "")},
    }


def earnings_calendar(symbol: str = "", horizon: str = "3month") -> dict:
    """Get upcoming earnings calendar rows from Alpha Vantage.

    Args:
        symbol: Optional stock ticker symbol. Leave empty for broader upcoming earnings.
        horizon: Alpha Vantage horizon value, usually 3month, 6month, or 12month.
    """
    print(f"(earnings_calendar {symbol or 'ALL'}, horizon={horizon})")
    params = {
        "function": "EARNINGS_CALENDAR",
        "horizon": horizon,
    }
    if symbol:
        params["symbol"] = symbol.upper()

    rows = _alpha_vantage_csv(params)
    if isinstance(rows, dict):
        return {"symbol": symbol.upper() if symbol else None, "source": "alpha_vantage", **rows}

    return {
        "symbol": symbol.upper() if symbol else None,
        "horizon": horizon,
        "source": "alpha_vantage",
        "rows": len(rows),
        "earnings": rows[:20],
    }


def economic_indicator(indicator: str, interval: str = "monthly", limit: int = 120) -> dict:
    """Get a macroeconomic indicator from Alpha Vantage.

    Args:
        indicator: One of CPI, FEDERAL_FUNDS_RATE, UNEMPLOYMENT, NONFARM_PAYROLL, INFLATION, RETAIL_SALES.
        interval: monthly, quarterly, or annual where supported by the endpoint.
        limit: Maximum number of rows to return after sorting by date.
    """
    normalized = indicator.strip().upper()
    supported = {
        "CPI",
        "FEDERAL_FUNDS_RATE",
        "UNEMPLOYMENT",
        "NONFARM_PAYROLL",
        "INFLATION",
        "RETAIL_SALES",
    }
    if normalized not in supported:
        return {
            "indicator": indicator,
            "source": "alpha_vantage",
            "error_type": "unsupported_indicator",
            "error": f"Supported indicators: {', '.join(sorted(supported))}",
        }

    print(f"(economic_indicator {normalized}, interval={interval})")
    params = {"function": normalized}
    if normalized != "INFLATION":
        params["interval"] = interval

    payload = _alpha_vantage_json(params)
    if "error_type" in payload:
        return {"indicator": normalized, "source": "alpha_vantage", **payload}

    data = payload.get("data", [])
    sorted_data = sorted(data, key=lambda row: row.get("date", ""))
    limited_data = sorted_data[-limit:] if limit > 0 else sorted_data
    return {
        "indicator": normalized,
        "interval": interval if normalized != "INFLATION" else "annual",
        "source": "alpha_vantage",
        "rows": len(data),
        "data": limited_data,
        "recent_data": limited_data[-12:],
    }


RECOMMENDATION_UNIVERSE = [
    {
        "symbol": "NVDA",
        "name": "NVIDIA",
        "sector": "Technology",
        "themes": ["AI", "Semiconductor"],
        "risk": "medium",
        "horizons": ["3m", "6m", "12m"],
        "styles": ["growth", "momentum", "quality"],
        "score": 88,
        "breakdown": {"momentum": 91, "quality": 86, "valuation": 48, "event": 82, "risk": 62},
        "thesis": "AI accelerator demand and data-center spending keep NVDA near the center of the market's growth narrative.",
        "reasons": [
            "Strong theme fit across AI infrastructure and semiconductors.",
            "High-quality profitability profile compared with most growth names.",
            "Potential catalysts from earnings, product cycles, and hyperscaler capex commentary.",
        ],
        "risks": [
            "Valuation leaves little room for execution misses.",
            "Export rules and supply-chain constraints can shift sentiment quickly.",
        ],
        "events": ["Earnings", "AI infrastructure demand updates", "Semiconductor cycle data"],
    },
    {
        "symbol": "MSFT",
        "name": "Microsoft",
        "sector": "Technology",
        "themes": ["AI", "Mega-cap Tech"],
        "risk": "low",
        "horizons": ["3m", "6m", "12m"],
        "styles": ["quality", "growth"],
        "score": 84,
        "breakdown": {"momentum": 74, "quality": 92, "valuation": 58, "event": 72, "risk": 82},
        "thesis": "Microsoft offers a steadier AI and cloud compounder profile with lower single-product risk.",
        "reasons": [
            "Durable cloud and enterprise software base.",
            "AI monetization can show up across Azure, Copilot, and developer tools.",
            "Lower risk profile than most high-beta AI names.",
        ],
        "risks": [
            "Growth expectations are already high.",
            "Cloud optimization cycles can pressure near-term revenue growth.",
        ],
        "events": ["Cloud revenue updates", "Copilot adoption", "Fed rate expectations"],
    },
    {
        "symbol": "TSM",
        "name": "Taiwan Semiconductor",
        "sector": "Technology",
        "themes": ["Semiconductor", "AI"],
        "risk": "medium",
        "horizons": ["3m", "6m", "12m"],
        "styles": ["quality", "growth"],
        "score": 81,
        "breakdown": {"momentum": 78, "quality": 88, "valuation": 64, "event": 76, "risk": 58},
        "thesis": "TSM is a core foundry exposure for AI, advanced nodes, and high-performance computing supply chains.",
        "reasons": [
            "Direct leverage to leading-edge semiconductor demand.",
            "Strong competitive position in advanced process nodes.",
            "Monthly revenue and capex commentary can provide frequent catalysts.",
        ],
        "risks": [
            "Geopolitical risk is structurally important.",
            "Semiconductor demand remains cyclical.",
        ],
        "events": ["Monthly sales", "Capex guidance", "Customer demand commentary"],
    },
    {
        "symbol": "RKLB",
        "name": "Rocket Lab",
        "sector": "Industrials",
        "themes": ["Space", "Defense"],
        "risk": "high",
        "horizons": ["3m", "6m", "12m"],
        "styles": ["growth", "event-driven", "momentum"],
        "score": 79,
        "breakdown": {"momentum": 86, "quality": 52, "valuation": 38, "event": 88, "risk": 34},
        "thesis": "RKLB is a high-beta space and defense candidate where contract flow and launch cadence can drive attention.",
        "reasons": [
            "Strong event-driven profile around launches, backlog, and defense contracts.",
            "Space systems revenue can broaden the story beyond launch services.",
            "High volatility creates research opportunities for active investors.",
        ],
        "risks": [
            "Execution risk is high relative to mature aerospace names.",
            "Valuation can be sensitive to rates and risk appetite.",
        ],
        "events": ["Launch cadence", "Defense contracts", "Earnings"],
    },
    {
        "symbol": "AVGO",
        "name": "Broadcom",
        "sector": "Technology",
        "themes": ["Semiconductor", "AI"],
        "risk": "medium",
        "horizons": ["3m", "6m", "12m"],
        "styles": ["quality", "growth", "momentum"],
        "score": 78,
        "breakdown": {"momentum": 82, "quality": 84, "valuation": 52, "event": 74, "risk": 59},
        "thesis": "Broadcom combines AI networking exposure with software cash-flow durability.",
        "reasons": [
            "AI networking and custom silicon remain relevant themes.",
            "Infrastructure software business can stabilize cash flow.",
            "Margin profile supports quality scoring.",
        ],
        "risks": [
            "Large acquisitions can complicate clean growth analysis.",
            "Semiconductor cycle risk still matters.",
        ],
        "events": ["AI networking demand", "VMware integration", "Earnings"],
    },
    {
        "symbol": "LLY",
        "name": "Eli Lilly",
        "sector": "Healthcare",
        "themes": ["Biotech", "Healthcare"],
        "risk": "medium",
        "horizons": ["6m", "12m"],
        "styles": ["growth", "quality"],
        "score": 76,
        "breakdown": {"momentum": 72, "quality": 86, "valuation": 42, "event": 77, "risk": 64},
        "thesis": "LLY remains a high-quality healthcare growth candidate tied to obesity and diabetes drug demand.",
        "reasons": [
            "Large addressable market in metabolic health.",
            "Healthcare exposure can diversify technology-heavy watchlists.",
            "Pipeline and capacity updates can create catalysts.",
        ],
        "risks": [
            "Valuation is demanding.",
            "Regulatory, reimbursement, and manufacturing constraints can affect expectations.",
        ],
        "events": ["Drug demand updates", "Pipeline data", "Regulatory decisions"],
    },
    {
        "symbol": "AMD",
        "name": "Advanced Micro Devices",
        "sector": "Technology",
        "themes": ["AI", "Semiconductor"],
        "risk": "high",
        "horizons": ["3m", "6m", "12m"],
        "styles": ["growth", "momentum", "event-driven"],
        "score": 74,
        "breakdown": {"momentum": 77, "quality": 68, "valuation": 44, "event": 84, "risk": 42},
        "thesis": "AMD is a higher-beta AI and compute candidate where product execution can change expectations quickly.",
        "reasons": [
            "AI GPU traction is a clear upside debate.",
            "CPU share and data-center commentary can move sentiment.",
            "Event-driven setup around product launches and earnings.",
        ],
        "risks": [
            "Competitive pressure from NVIDIA remains intense.",
            "High expectations can create sharp drawdowns.",
        ],
        "events": ["AI GPU updates", "Product launches", "Data-center revenue"],
    },
    {
        "symbol": "NEE",
        "name": "NextEra Energy",
        "sector": "Utilities",
        "themes": ["Energy", "Infrastructure"],
        "risk": "low",
        "horizons": ["6m", "12m"],
        "styles": ["quality", "value"],
        "score": 69,
        "breakdown": {"momentum": 58, "quality": 76, "valuation": 68, "event": 55, "risk": 78},
        "thesis": "NEE is a lower-risk infrastructure and clean-energy candidate with rate sensitivity.",
        "reasons": [
            "Defensive sector exposure can balance high-growth candidates.",
            "Renewables and power demand themes remain relevant.",
            "Potential beneficiary if rate pressure eases.",
        ],
        "risks": [
            "Rates can pressure utility valuations.",
            "Project execution and regulatory risk matter.",
        ],
        "events": ["Fed meetings", "Power demand data", "Regulatory updates"],
    },
]


def stock_recommendations(
    theme: str = "all",
    risk: str = "all",
    horizon: str = "3m",
    style: str = "growth",
    limit: int = 10,
    source: str = "prototype",
    futu_group: str = "",
) -> dict:
    """Return research candidate stocks from a deterministic prototype scoring model."""
    if source.strip().lower() == "futu":
        return futu_stock_recommendations(group_name=futu_group, limit=limit)

    normalized_theme = theme.strip().lower()
    normalized_risk = risk.strip().lower()
    normalized_horizon = horizon.strip().lower()
    normalized_style = style.strip().lower()

    candidates = []
    for stock in RECOMMENDATION_UNIVERSE:
        theme_match = normalized_theme == "all" or any(
            item.lower().replace(" ", "-") == normalized_theme for item in stock["themes"]
        )
        risk_match = normalized_risk == "all" or stock["risk"] == normalized_risk
        horizon_match = normalized_horizon == "all" or normalized_horizon in stock["horizons"]
        style_match = normalized_style == "all" or normalized_style in stock["styles"]

        if not (theme_match and risk_match and horizon_match and style_match):
            continue

        adjusted_score = stock["score"]
        if normalized_theme != "all" and theme_match:
            adjusted_score += 3
        if normalized_style != "all" and style_match:
            adjusted_score += 2
        if normalized_risk != "all" and risk_match:
            adjusted_score += 1

        candidates.append({**stock, "score": min(adjusted_score, 99)})

    candidates = sorted(candidates, key=lambda item: item["score"], reverse=True)[:limit]

    return {
        "source": "prototype_scoring_model",
        "universe_size": len(RECOMMENDATION_UNIVERSE),
        "filters": {
            "source": source,
            "theme": theme,
            "risk": risk,
            "horizon": horizon,
            "style": style,
        },
        "recommendations": candidates,
    }


def _futu_opend_config() -> tuple[str, int]:
    host = os.getenv("FUTU_OPEND_HOST", "127.0.0.1")
    try:
        port = int(os.getenv("FUTU_OPEND_PORT", "11111"))
    except ValueError:
        port = 11111
    return host, port


def _futu_opend_unavailable_error(host: str, port: int) -> dict | None:
    try:
        with socket.create_connection((host, port), timeout=1):
            return None
    except OSError as error:
        return {
            "source": "futu_opend",
            "host": host,
            "port": port,
            "error_type": "futu_opend_unavailable",
            "error": f"Cannot connect to Futu OpenD at {host}:{port}. Start Futu OpenD and log in first. {error}",
        }


def _dataframe_records(data) -> list[dict]:
    if not hasattr(data, "to_dict"):
        return []

    cleaned = data.where(pd.notnull(data), None)
    return cleaned.to_dict(orient="records")


def _extract_futu_group_name(row: dict) -> str | None:
    for key in ("group_name", "name", "group"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _normalize_futu_security(row: dict, group_name: str) -> dict:
    code = str(row.get("code") or "")
    market = ""
    symbol = code
    if "." in code:
        market, symbol = code.split(".", 1)

    return {
        "code": code,
        "symbol": symbol,
        "market": market,
        "name": row.get("name") or row.get("stock_name") or symbol,
        "group": group_name,
        "raw": row,
    }


def futu_user_security_groups(group_type: str = "ALL") -> dict:
    """Get Futu user security groups from local Futu OpenD."""
    host, port = _futu_opend_config()
    unavailable = _futu_opend_unavailable_error(host, port)
    if unavailable:
        return unavailable

    try:
        from futu import OpenQuoteContext, RET_OK
    except ImportError as error:
        return {
            "source": "futu_opend",
            "error_type": "missing_dependency",
            "error": f"futu-api is not installed: {error}",
        }

    quote_ctx = OpenQuoteContext(host=host, port=port)
    try:
        ret, data = quote_ctx.get_user_security_group(group_type=group_type)
    except Exception as error:
        return {
            "source": "futu_opend",
            "host": host,
            "port": port,
            "error_type": type(error).__name__,
            "error": str(error),
        }
    finally:
        quote_ctx.close()

    if ret != RET_OK:
        return {
            "source": "futu_opend",
            "host": host,
            "port": port,
            "error_type": "futu_api_error",
            "error": str(data),
        }

    groups = _dataframe_records(data)
    return {
        "source": "futu_opend",
        "host": host,
        "port": port,
        "groups": groups,
    }


def futu_watchlist(group_name: str = "", group_type: str = "ALL") -> dict:
    """Get stocks from Futu watchlist groups through local Futu OpenD."""
    host, port = _futu_opend_config()
    unavailable = _futu_opend_unavailable_error(host, port)
    if unavailable:
        return unavailable

    try:
        from futu import OpenQuoteContext, RET_OK
    except ImportError as error:
        return {
            "source": "futu_opend",
            "error_type": "missing_dependency",
            "error": f"futu-api is not installed: {error}",
        }

    quote_ctx = OpenQuoteContext(host=host, port=port)
    try:
        if group_name.strip():
            group_names = [group_name.strip()]
            group_rows = [{"group_name": group_name.strip()}]
        else:
            ret, group_data = quote_ctx.get_user_security_group(group_type=group_type)
            if ret != RET_OK:
                return {
                    "source": "futu_opend",
                    "host": host,
                    "port": port,
                    "error_type": "futu_api_error",
                    "error": str(group_data),
                }

            group_rows = _dataframe_records(group_data)
            group_names = [
                name
                for name in (_extract_futu_group_name(row) for row in group_rows)
                if name
            ]

        stocks_by_code: dict[str, dict] = {}
        group_errors = []
        for name in group_names:
            ret, security_data = quote_ctx.get_user_security(name)
            if ret != RET_OK:
                group_errors.append({"group": name, "error": str(security_data)})
                continue

            for row in _dataframe_records(security_data):
                stock = _normalize_futu_security(row, name)
                if stock["code"]:
                    stocks_by_code.setdefault(stock["code"], stock)

        return {
            "source": "futu_opend",
            "host": host,
            "port": port,
            "groups": group_rows,
            "group_names": group_names,
            "group_errors": group_errors,
            "rows": len(stocks_by_code),
            "stocks": list(stocks_by_code.values()),
        }
    except Exception as error:
        return {
            "source": "futu_opend",
            "host": host,
            "port": port,
            "error_type": type(error).__name__,
            "error": str(error),
        }
    finally:
        quote_ctx.close()


def futu_stock_recommendations(group_name: str = "", limit: int = 10) -> dict:
    watchlist = futu_watchlist(group_name=group_name)
    if "error_type" in watchlist:
        return watchlist

    candidates = []
    for index, stock in enumerate(watchlist.get("stocks", [])[:limit]):
        score = max(52, 72 - index)
        candidates.append(
            {
                "symbol": stock["symbol"],
                "code": stock["code"],
                "name": stock["name"],
                "sector": "Futu Watchlist",
                "themes": ["Futu Watchlist"],
                "risk": "medium",
                "horizons": ["3m", "6m", "12m"],
                "styles": ["watchlist", "research"],
                "score": score,
                "breakdown": {
                    "momentum": 60,
                    "quality": 60,
                    "valuation": 50,
                    "event": 58,
                    "risk": 55,
                },
                "thesis": f"{stock['name']} is in your Futu watchlist, so it is included as a personal research candidate.",
                "reasons": [
                    "This stock comes from your own Futu watchlist instead of the prototype universe.",
                    "It can now enter the same recommendation workflow as the built-in candidate stocks.",
                    "The next step is to enrich it with price, fundamentals, earnings, and news data.",
                ],
                "risks": [
                    "This first Futu version does not calculate live factor scores yet.",
                    "Scores are placeholder research-priority scores until market data enrichment is added.",
                ],
                "events": ["Watchlist review", "Price data enrichment", "Earnings check"],
            }
        )

    return {
        "source": "futu_opend",
        "universe_size": watchlist.get("rows", 0),
        "filters": {
            "source": "futu",
            "group_name": group_name,
        },
        "groups": watchlist.get("group_names", []),
        "group_errors": watchlist.get("group_errors", []),
        "recommendations": candidates,
    }
