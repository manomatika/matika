from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
import asyncio
import random
import logging
import yfinance as yf
from curl_cffi.requests import AsyncSession
from ..database import SecurityType, AssetClass

logger = logging.getLogger(__name__)

class BaseSecurityEndpoint(ABC):
    """Abstract base class for all security data providers."""
    
    @abstractmethod
    async def search(self, query: str) -> List[Dict[str, str]]:
        """Search for securities by name or symbol. Returns list of {symbol, name, type, exchange}."""
        pass

    @abstractmethod
    async def lookup(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed metadata for a specific symbol."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Returns the display name of this endpoint."""
        pass

    def _map_security_type(self, yahoo_type: str) -> str:
        mapping = {
            "EQUITY": SecurityType.STOCK.value,
            "ETF": SecurityType.ETF.value,
            "MUTUALFUND": SecurityType.MUTUAL_FUND.value,
            "MONEYMARKET": SecurityType.MUTUAL_FUND.value,  # MMFs are Mutual Funds
            "BOND": SecurityType.BOND.value
        }
        return mapping.get(yahoo_type, SecurityType.STOCK.value)

    def _infer_asset_class(self, info: Dict) -> Optional[str]:
        y_type = info.get("quoteType")
        if y_type == "MONEYMARKET":
            return AssetClass.MONEY_MARKET.value
        
        category = info.get("category", "")
        long_name = info.get("longName", "") or info.get("shortName", "")
        summary = info.get("longBusinessSummary", "")
        
        text_to_check = f"{category} {long_name} {summary}".lower()
        
        if "small" in text_to_check:
            return AssetClass.SMALL_CAP_STOCK.value
        if "mid" in text_to_check:
            # We don't have MID_CAP in AssetClass enum, default to LARGE or SMALL?
            # Existing enum has LARGE_CAP and SMALL_CAP.
            return AssetClass.LARGE_CAP_STOCK.value
        if "large" in text_to_check or "total market" in text_to_check or "s&p 500" in text_to_check:
            return AssetClass.LARGE_CAP_STOCK.value
        if "bond" in text_to_check:
            return AssetClass.DOMESTIC_BOND.value
            
        if y_type == "EQUITY":
            return AssetClass.LARGE_CAP_STOCK.value
            
        return None

class YahooScraperEndpoint(BaseSecurityEndpoint):
    """Matika Standard (Yahoo Scraper) - Uses curl_cffi and yfinance."""
    
    SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Origin": "https://finance.yahoo.com",
        "Referer": "https://finance.yahoo.com/"
    }

    def get_name(self) -> str:
        return "Matika Standard (Yahoo Scraper)"

    async def search(self, query: str) -> List[Dict[str, str]]:
        params = {"q": query, "quotesCount": 20, "newsCount": 0}
        try:
            async with AsyncSession(impersonate="chrome110") as s:
                await asyncio.sleep(random.uniform(0.1, 0.3))
                response = await s.get(self.SEARCH_URL, params=params, headers=self.HEADERS)
                if response.status_code == 429:
                    raise Exception("Yahoo rate limited (429)")
                if response.status_code != 200:
                    return []
                
                data = response.json()
                results = []
                for quote in data.get("quotes", []):
                    results.append({
                        "symbol": quote.get("symbol"),
                        "name": quote.get("shortname") or quote.get("longname") or quote.get("symbol"),
                        "type": quote.get("quoteType"),
                        "exchange": quote.get("exchange")
                    })
                
                # (2) Fallback: if no results, but query looks like a ticker (e.g. VUSXX), add virtual result
                clean_query = query.strip().upper()
                # Tickers are typically 1-10 chars, letters, numbers, dots, or dashes
                if not results and clean_query and len(clean_query) <= 10 and all(c.isalnum() or c in ".-" for c in clean_query):
                    results.append({
                        "symbol": clean_query,
                        "name": f"Check details for {clean_query}",
                        "type": "UNKNOWN",
                        "exchange": "N/A"
                    })
                return results
        except Exception as e:
            logger.error(f"Yahoo search error: {e}")
            if "rate limited" in str(e).lower():
                raise
            return []

    async def lookup(self, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, lambda: yf.Ticker(symbol).info)
            if not info or 'symbol' not in info:
                return None
            
            quote_type = info.get("quoteType")
            y_val = str(info.get("yield", ""))
            
            return {
                "symbol": symbol,
                "name": info.get("longName") or info.get("shortName") or symbol,
                "security_type": self._map_security_type(quote_type),
                "asset_class": self._infer_asset_class(info),
                "current_price": str(info.get("regularMarketPrice", "")),
                "previous_close": str(info.get("regularMarketPreviousClose", "")),
                "open_price": str(info.get("regularMarketOpen", "")),
                "nav": str(info.get("navPrice", "")),
                "range_52_week": info.get("fiftyTwoWeekRange", ""),
                "avg_volume": str(info.get("averageDailyVolume3Month", "")),
                # (2) For MMF, yield is SEC 7-day. (3) For others, yield is SEC 30-day.
                "yield_30_day": y_val if quote_type != "MONEYMARKET" else "",
                "yield_7_day": y_val if quote_type == "MONEYMARKET" else ""
            }
        except Exception as e:
            logger.error(f"Yahoo lookup error for '{symbol}': {e}")
            return None

class FinnhubEndpoint(BaseSecurityEndpoint):
    """Finnhub API - Reliable, requires API key."""
    
    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_name(self) -> str:
        return "Finnhub API"

    async def search(self, query: str) -> List[Dict[str, str]]:
        if not self.api_key: return []
        url = f"{self.BASE_URL}/search"
        params = {"q": query, "token": self.api_key}
        async with AsyncSession() as s:
            response = await s.get(url, params=params)
            if response.status_code == 429: raise Exception("Finnhub rate limited")
            if response.status_code != 200: return []
            
            data = response.json()
            results = []
            for item in data.get("result", []):
                results.append({
                    "symbol": item.get("symbol"),
                    "name": item.get("description"),
                    "type": item.get("type"),
                    "exchange": item.get("displaySymbol")
                })
            return results

    async def lookup(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.api_key: return None
        # Finnhub needs two calls: quote and profile2
        async with AsyncSession() as s:
            # Get Quote
            q_url = f"{self.BASE_URL}/quote"
            q_resp = await s.get(q_url, params={"symbol": symbol, "token": self.api_key})
            
            # Get Profile
            p_url = f"{self.BASE_URL}/stock/profile2"
            p_resp = await s.get(p_url, params={"symbol": symbol, "token": self.api_key})
            
            if q_resp.status_code != 200 or p_resp.status_code != 200:
                return None
            
            q_data = q_resp.json()
            p_data = p_resp.json()
            
            return {
                "symbol": symbol,
                "name": p_data.get("name") or symbol,
                "security_type": self._map_security_type(p_data.get("quoteType", "EQUITY")),
                "asset_class": None, # Finnhub profile is limited on free tier
                "current_price": str(q_data.get("c", "")),
                "previous_close": str(q_data.get("pc", "")),
                "open_price": str(q_data.get("o", "")),
                "nav": "",
                "range_52_week": f"{q_data.get('l', '')} - {q_data.get('h', '')}",
                "avg_volume": "",
                "yield_30_day": "",
                "yield_7_day": ""
            }

class AlphaVantageEndpoint(BaseSecurityEndpoint):
    """Alpha Vantage API - Reliable backup, requires API key."""
    
    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_name(self) -> str:
        return "Alpha Vantage API"

    async def search(self, query: str) -> List[Dict[str, str]]:
        if not self.api_key: return []
        params = {
            "function": "SYMBOL_SEARCH",
            "keywords": query,
            "apikey": self.api_key
        }
        async with AsyncSession() as s:
            response = await s.get(self.BASE_URL, params=params)
            if response.status_code != 200: return []
            data = response.json()
            if "Note" in data: raise Exception("Alpha Vantage rate limited")
            
            results = []
            for item in data.get("bestMatches", []):
                results.append({
                    "symbol": item.get("1. symbol"),
                    "name": item.get("2. name"),
                    "type": item.get("3. type"),
                    "exchange": item.get("4. region")
                })
            return results

    async def lookup(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.api_key: return None
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": self.api_key
        }
        async with AsyncSession() as s:
            response = await s.get(self.BASE_URL, params=params)
            if response.status_code != 200: return None
            data = response.json().get("Global Quote", {})
            if not data: return None
            
            return {
                "symbol": symbol,
                "name": symbol, # Global quote doesn't return name
                "security_type": SecurityType.STOCK.value,
                "asset_class": None,
                "current_price": data.get("05. price", ""),
                "previous_close": data.get("08. previous close", ""),
                "open_price": data.get("02. open", ""),
                "nav": "",
                "range_52_week": f"{data.get('04. low', '')} - {data.get('03. high', '')}",
                "avg_volume": data.get("06. volume", ""),
                "yield_30_day": "",
                "yield_7_day": ""
            }
