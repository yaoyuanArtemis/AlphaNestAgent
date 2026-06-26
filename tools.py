from pathlib import Path
import csv
import json
import os
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
