from datetime import datetime
import httpx
from app.market_data.base import BaseMarketProvider, PriceBar
from app.core.exceptions import ProviderError
from app.core.logging import get_logger
from app.config import settings

logger = get_logger(__name__)

# Binance uses USDT-paired symbols
SYMBOL_MAP = {
    "BTC":  "BTCUSDT",
    "ETH":  "ETHUSDT",
    "BTCUSDT": "BTCUSDT",
    "ETHUSDT": "ETHUSDT",
}


class BinanceProvider(BaseMarketProvider):
    @property
    def name(self) -> str:
        return "binance"

    def fetch_prices(self, symbols: list[str]) -> list[PriceBar]:
        results = []
        for sym in symbols:
            binance_sym = SYMBOL_MAP.get(sym.upper())
            if not binance_sym:
                continue
            try:
                bar = self._fetch_ticker(binance_sym, sym)
                if bar:
                    results.append(bar)
            except ProviderError:
                logger.warning(f"Binance: skipping {sym} after fetch failure")
        return results

    def _fetch_ticker(self, binance_symbol: str, canonical_symbol: str) -> PriceBar:
        url = f"{settings.binance_base_url}/api/v3/ticker/24hr"
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(url, params={"symbol": binance_symbol})
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            raise ProviderError(f"Binance fetch failed for {binance_symbol}: {e}") from e

        try:
            return PriceBar(
                symbol=canonical_symbol.upper(),
                asset_class="crypto",
                open=float(data["openPrice"]),
                high=float(data["highPrice"]),
                low=float(data["lowPrice"]),
                close=float(data["lastPrice"]),
                volume=float(data["volume"]),
                source=self.name,
                fetched_at=datetime.utcnow(),
            )
        except (KeyError, ValueError) as e:
            raise ProviderError(f"Binance: malformed response for {binance_symbol}: {e}") from e
