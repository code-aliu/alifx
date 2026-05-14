from datetime import datetime
import httpx
from app.market_data.base import BaseMarketProvider, PriceBar
from app.core.exceptions import ProviderError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Yahoo Finance ticker symbols for our stock universe
SYMBOL_MAP = {
    "SPY":  "SPY",
    "QQQ":  "QQQ",
    "NVDA": "NVDA",
    "AAPL": "AAPL",
}

YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


class YahooFinanceProvider(BaseMarketProvider):
    @property
    def name(self) -> str:
        return "yahoo"

    def fetch_prices(self, symbols: list[str]) -> list[PriceBar]:
        results = []
        for sym in symbols:
            yahoo_sym = SYMBOL_MAP.get(sym.upper())
            if not yahoo_sym:
                continue
            try:
                bar = self._fetch_ticker(yahoo_sym)
                if bar:
                    results.append(bar)
            except ProviderError:
                logger.warning(f"Yahoo: skipping {sym} after fetch failure")
        return results

    def _fetch_ticker(self, symbol: str) -> PriceBar:
        url = YAHOO_QUOTE_URL.format(symbol=symbol)
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            with httpx.Client(timeout=15, headers=headers) as client:
                resp = client.get(url, params={"interval": "1d", "range": "1d"})
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            raise ProviderError(f"Yahoo fetch failed for {symbol}: {e}") from e

        try:
            meta = data["chart"]["result"][0]["meta"]
            return PriceBar(
                symbol=symbol,
                asset_class="stock",
                open=float(meta.get("chartPreviousClose", meta["regularMarketPrice"])),
                high=float(meta["regularMarketDayHigh"]),
                low=float(meta["regularMarketDayLow"]),
                close=float(meta["regularMarketPrice"]),
                volume=float(meta.get("regularMarketVolume", 0)),
                source=self.name,
                fetched_at=datetime.utcnow(),
            )
        except (KeyError, IndexError, ValueError) as e:
            raise ProviderError(f"Yahoo: malformed response for {symbol}: {e}") from e
