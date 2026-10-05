import os
import sys
import json
import datetime
from pathlib import Path
from typing import Dict, Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import requests
from backend.config import settings, rate_limiter
from backend.graph.state import FinSightState

TICKER_MAP = {
    "apple": "AAPL",
    "aapl": "AAPL",
    "microsoft": "MSFT",
    "msft": "MSFT",
    "nvidia": "NVDA",
    "nvda": "NVDA",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "googl": "GOOGL",
    "goog": "GOOGL",
    "amazon": "AMZN",
    "amzn": "AMZN",
    "meta": "META",
    "facebook": "META",
    "tesla": "TSLA",
    "tsla": "TSLA",
    "netflix": "NFLX",
    "nflx": "NFLX"
}

def get_ticker_for_company(company: str) -> str:
    cleaned = company.lower().strip()
    for name, ticker in TICKER_MAP.items():
        if name in cleaned:
            return ticker
    return company.upper()

def get_cache_path(ticker: str, endpoint: str, date_str: str) -> Path:
    filename = f"{ticker}_{endpoint}_{date_str}.json"
    return settings.CACHE_DIR / filename

def fetch_alpha_vantage(function: str, symbol: str) -> Dict[str, Any]:
    """
    Fetches Alpha Vantage endpoint with local disk caching and shared rate limiting.
    """
    today_str = datetime.date.today().isoformat()
    cache_file = get_cache_path(symbol, function, today_str)

    # 1. Check local cache
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data and not data.get("Note") and not data.get("Information"):
                    data["_provenance"] = "cached"
                    data["_cache_date"] = today_str
                    return data
        except Exception:
            pass

    # 2. Rate limit and call live API
    if not settings.ALPHA_VANTAGE_API_KEY:
        if not settings.ALLOW_MOCK_DATA:
            return {
                "_provenance": "unavailable",
                "limitation": "Alpha Vantage API key not configured. Live market data unavailable."
            }
        mock = _mock_market_data_fallback(symbol, function)
        mock["_provenance"] = "mock_fixture"
        return mock

    try:
        rate_limiter.acquire()
        url = "https://www.alphavantage.co/query"
        params = {
            "function": function,
            "symbol": symbol,
            "apikey": settings.ALPHA_VANTAGE_API_KEY
        }
        resp = requests.get(url, params=params, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            # If Alpha Vantage sends rate limit warning message
            if "Note" in data or "Information" in data:
                print(f"Alpha Vantage API limit notice: {data.get('Note') or data.get('Information')}")
                if not settings.ALLOW_MOCK_DATA:
                    return {
                        "_provenance": "unavailable",
                        "limitation": f"Alpha Vantage rate limit reached for {symbol} ({function})."
                    }
                mock = _mock_market_data_fallback(symbol, function)
                mock["_provenance"] = "mock_fixture"
                return mock

            # Save to disk cache
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            data["_provenance"] = "live"
            return data
    except Exception as e:
        print(f"Alpha Vantage request error ({function} for {symbol}): {e}")

    if not settings.ALLOW_MOCK_DATA:
        return {
            "_provenance": "unavailable",
            "limitation": f"Live market data unavailable for {symbol} ({function}): network error."
        }
    mock = _mock_market_data_fallback(symbol, function)
    mock["_provenance"] = "mock_fixture"
    return mock

def _mock_market_data_fallback(symbol: str, function: str) -> Dict[str, Any]:
    """Reliable fallback data based on recent market figures if API key is exhausted or unavailable."""
    snapshots = {
        "AAPL": {
            "GLOBAL_QUOTE": {
                "01. symbol": "AAPL",
                "05. price": "234.80",
                "08. previous close": "232.50",
                "09. change": "2.30",
                "10. change percent": "0.9893%",
                "06. volume": "48200000"
            },
            "OVERVIEW": {
                "Symbol": "AAPL",
                "Name": "Apple Inc",
                "MarketCapitalization": "3580000000000",
                "PERatio": "34.5",
                "52WeekHigh": "237.23",
                "52WeekLow": "164.08",
                "DividendYield": "0.0044",
                "EPS": "6.72"
            }
        },
        "MSFT": {
            "GLOBAL_QUOTE": {
                "01. symbol": "MSFT",
                "05. price": "448.20",
                "08. previous close": "445.10",
                "09. change": "3.10",
                "10. change percent": "0.6965%",
                "06. volume": "21300000"
            },
            "OVERVIEW": {
                "Symbol": "MSFT",
                "Name": "Microsoft Corporation",
                "MarketCapitalization": "3330000000000",
                "PERatio": "36.2",
                "52WeekHigh": "468.35",
                "52WeekLow": "309.45",
                "DividendYield": "0.0071",
                "EPS": "11.86"
            }
        },
        "NVDA": {
            "GLOBAL_QUOTE": {
                "01. symbol": "NVDA",
                "05. price": "128.50",
                "08. previous close": "125.80",
                "09. change": "2.70",
                "10. change percent": "2.1463%",
                "06. volume": "73400000"
            },
            "OVERVIEW": {
                "Symbol": "NVDA",
                "Name": "NVIDIA Corporation",
                "MarketCapitalization": "3150000000000",
                "PERatio": "48.1",
                "52WeekHigh": "140.76",
                "52WeekLow": "45.01",
                "DividendYield": "0.0003",
                "EPS": "2.68"
            }
        },
        "GOOGL": {
            "GLOBAL_QUOTE": {
                "01. symbol": "GOOGL",
                "05. price": "182.50",
                "08. previous close": "180.10",
                "09. change": "2.40",
                "10. change percent": "1.3326%",
                "06. volume": "22100000"
            },
            "OVERVIEW": {
                "Symbol": "GOOGL",
                "Name": "Alphabet Inc",
                "MarketCapitalization": "2250000000000",
                "PERatio": "24.8",
                "52WeekHigh": "191.75",
                "52WeekLow": "130.67",
                "DividendYield": "0.0044",
                "EPS": "7.54"
            }
        },
        "GOOG": {
            "GLOBAL_QUOTE": {
                "01. symbol": "GOOG",
                "05. price": "183.10",
                "08. previous close": "180.70",
                "09. change": "2.40",
                "10. change percent": "1.3282%",
                "06. volume": "18500000"
            },
            "OVERVIEW": {
                "Symbol": "GOOG",
                "Name": "Alphabet Inc",
                "MarketCapitalization": "2250000000000",
                "PERatio": "24.9",
                "52WeekHigh": "193.31",
                "52WeekLow": "131.55",
                "DividendYield": "0.0044",
                "EPS": "7.54"
            }
        },
        "AMZN": {
            "GLOBAL_QUOTE": {
                "01. symbol": "AMZN",
                "05. price": "186.40",
                "08. previous close": "184.20",
                "09. change": "2.20",
                "10. change percent": "1.1943%",
                "06. volume": "35400000"
            },
            "OVERVIEW": {
                "Symbol": "AMZN",
                "Name": "Amazon.com Inc",
                "MarketCapitalization": "1940000000000",
                "PERatio": "44.2",
                "52WeekHigh": "201.20",
                "52WeekLow": "118.35",
                "DividendYield": "0.0",
                "EPS": "4.22"
            }
        },
        "META": {
            "GLOBAL_QUOTE": {
                "01. symbol": "META",
                "05. price": "582.00",
                "08. previous close": "576.20",
                "09. change": "5.80",
                "10. change percent": "1.0066%",
                "06. volume": "14200000"
            },
            "OVERVIEW": {
                "Symbol": "META",
                "Name": "Meta Platforms Inc",
                "MarketCapitalization": "1470000000000",
                "PERatio": "28.6",
                "52WeekHigh": "602.95",
                "52WeekLow": "279.40",
                "DividendYield": "0.0034",
                "EPS": "20.35"
            }
        },
        "TSLA": {
            "GLOBAL_QUOTE": {
                "01. symbol": "TSLA",
                "05. price": "248.50",
                "08. previous close": "242.10",
                "09. change": "6.40",
                "10. change percent": "2.6435%",
                "06. volume": "68500000"
            },
            "OVERVIEW": {
                "Symbol": "TSLA",
                "Name": "Tesla Inc",
                "MarketCapitalization": "790000000000",
                "PERatio": "62.4",
                "52WeekHigh": "271.00",
                "52WeekLow": "138.80",
                "DividendYield": "0.0",
                "EPS": "3.98"
            }
        }
    }
    return snapshots.get(symbol, {}).get(function, {})

def execute_market_data(state: FinSightState, sse_callback=None) -> Dict[str, Any]:
    """
    Market Data Agent: fetches price and fundamentals with disk caching and rate limiting.
    """
    companies = state.get("companies", ["NVIDIA"])
    market_data = dict(state.get("market_data", {}))

    for company in companies:
        ticker = get_ticker_for_company(company)
        if sse_callback:
            sse_callback({
                "agent": "market_data",
                "status": "fetching_quotes",
                "company": company,
                "ticker": ticker
            })

        quote = fetch_alpha_vantage("GLOBAL_QUOTE", ticker)
        overview = fetch_alpha_vantage("OVERVIEW", ticker)

        quote_data = quote.get("Global Quote", quote)
        price = quote_data.get("05. price", "N/A")
        change_pct = quote_data.get("10. change percent", "N/A")
        market_cap = overview.get("MarketCapitalization", "N/A")
        pe_ratio = overview.get("PERatio", "N/A")
        high_52 = overview.get("52WeekHigh", "N/A")
        low_52 = overview.get("52WeekLow", "N/A")

        quote_prov = quote.get("_provenance", "unknown")
        overview_prov = overview.get("_provenance", "unknown")

        if quote_prov == "unavailable" and overview_prov == "unavailable":
            overall_prov = "unavailable"
            source_label = "Unavailable (Live API limitation)"
        elif quote_prov == "live" and overview_prov == "live":
            overall_prov = "live"
            source_label = "Alpha Vantage (Live)"
        elif quote_prov == "cached" and overview_prov == "cached":
            overall_prov = "cached"
            source_label = "Alpha Vantage (Local Cache)"
        elif "mock_fixture" in (quote_prov, overview_prov):
            overall_prov = "mock_fixture"
            source_label = "Mock Fixture (Offline Fallback)"
        else:
            overall_prov = "mixed"
            source_label = f"Quote: {quote_prov}, Fundamentals: {overview_prov}"

        market_data[company] = {
            "ticker": ticker,
            "price": price,
            "change_percent": change_pct,
            "market_cap": market_cap,
            "pe_ratio": pe_ratio,
            "52_week_high": high_52,
            "52_week_low": low_52,
            "quote_provenance": quote_prov,
            "overview_provenance": overview_prov,
            "source": source_label,
            "provenance": overall_prov,
            "date": datetime.date.today().isoformat()
        }

    return {
        "market_data": market_data
    }
