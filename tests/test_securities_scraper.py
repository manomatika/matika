import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from matika.securities.endpoints import YahooScraperEndpoint
from matika.database import SecurityType, AssetClass

@pytest.mark.asyncio
@patch("matika.securities.endpoints.AsyncSession")
async def test_yahoo_endpoint_search(mock_session):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "quotes": [
            {"symbol": "VOO", "shortname": "Vanguard S&P 500 ETF", "quoteType": "ETF", "exchange": "NYE"}
        ]
    }
    mock_session.return_value.__aenter__.return_value.get.return_value = mock_response
    
    endpoint = YahooScraperEndpoint()
    results = await endpoint.search("VOO")
    
    assert len(results) == 1
    assert results[0]["symbol"] == "VOO"
    assert results[0]["name"] == "Vanguard S&P 500 ETF"
    assert results[0]["type"] == "ETF"

@pytest.mark.asyncio
@patch("matika.securities.endpoints.yf.Ticker")
async def test_yahoo_endpoint_lookup(mock_ticker):
    mock_ticker.return_value.info = {
        "symbol": "VOO",
        "longName": "Vanguard S&P 500 ETF",
        "quoteType": "ETF",
        "regularMarketPrice": 450.12,
        "regularMarketPreviousClose": 448.00,
        "regularMarketOpen": 449.00,
        "navPrice": 450.10,
        "fiftyTwoWeekRange": "380.00 - 460.00",
        "averageDailyVolume3Month": 3000000,
        "yield": 0.015
    }
    
    endpoint = YahooScraperEndpoint()
    data = await endpoint.lookup("VOO")
    
    assert data is not None
    assert data["symbol"] == "VOO"
    assert data["name"] == "Vanguard S&P 500 ETF"
    assert data["security_type"] == SecurityType.ETF.value
    assert data["current_price"] == "450.12"
    assert data["yield_30_day"] == "0.015"
