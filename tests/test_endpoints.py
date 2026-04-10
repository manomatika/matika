import pytest
from unittest.mock import MagicMock, patch
from src.matika.securities.endpoints import YahooScraperEndpoint, FinnhubEndpoint, AlphaVantageEndpoint

@pytest.mark.asyncio
async def test_yahoo_endpoint_name():
    ep = YahooScraperEndpoint()
    assert ep.get_name() == "Matika Standard (Yahoo Scraper)"

@pytest.mark.asyncio
async def test_finnhub_endpoint_name():
    ep = FinnhubEndpoint(api_key="test")
    assert ep.get_name() == "Finnhub API"

@pytest.mark.asyncio
async def test_alpha_vantage_endpoint_name():
    ep = AlphaVantageEndpoint(api_key="test")
    assert ep.get_name() == "Alpha Vantage API"

@pytest.mark.asyncio
@patch("src.matika.securities.endpoints.yf.Ticker")
async def test_yahoo_lookup(mock_ticker):
    mock_ticker.return_value.info = {
        "symbol": "VOO",
        "longName": "Vanguard S&P 500 ETF",
        "quoteType": "ETF",
        "regularMarketPrice": 580.93
    }
    ep = YahooScraperEndpoint()
    result = await ep.lookup("VOO")
    assert result is not None
    assert result["symbol"] == "VOO"
    assert result["name"] == "Vanguard S&P 500 ETF"
    assert result["current_price"] == "580.93"

@pytest.mark.asyncio
@patch("src.matika.securities.endpoints.AsyncSession")
async def test_finnhub_search(mock_session):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "result": [
            {"symbol": "VOO", "description": "Vanguard S&P 500 ETF", "type": "ETF", "displaySymbol": "VOO"}
        ]
    }
    # Mocking the async context manager
    mock_session.return_value.__aenter__.return_value.get.return_value = mock_resp
    
    ep = FinnhubEndpoint(api_key="test")
    results = await ep.search("VOO")
    assert len(results) == 1
    assert results[0]["symbol"] == "VOO"
    assert results[0]["name"] == "Vanguard S&P 500 ETF"
