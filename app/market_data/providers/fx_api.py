from datetime import datetime
import httpx
from app.market_data.base import BaseMarketProvider, PriceBar
from app.core.exceptions import ProviderError
from app.core.logging import get_logger
from app.config import settings

logger = get_logger(__name__)

# Frankfurter.app is free, no API key required, covers major pairs
# Format: BASE_QUOTE → (base_currency, quote_currency)
PAIR_MAP = {
    "EURUSD": ("EUR", "USD"),
    "EUR/USD": ("EUR", "USD"),
    "USDJPY": ("USD", "JPY"),
    "USD/JPY": ("USD", "JPY"),
    "GBPUSD": ("GBP", "USD"),
    "GBP/USD": ("GBP", "USD"),
}


class FxApiProvider(BaseMarketProvider):
    @property
    def name(self) -> str:
        return "frankfurter"

    def fetch_prices(self, symbols: list[str]) -> list[PriceBar]:
        results = []
        for sym in symbols:
            pair = PAIR_MAP.get(sym.upper()) or PAIR_MAP.get(sym)
            if not pair:
                continue
            try:
                bar = self._fetch_pair(sym, pair[0], pair[1])
                if bar:
                    results.append(bar)
            except ProviderError:
                logger.warning(f"FxApi: skipping {sym} after fetch failure")
        return results

    def _fetch_pair(self, canonical: str, base: str, quote: str) -> PriceBar:
        url = f"{settings.fx_api_base_url}/latest"
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(url, params={"from": base, "to": quote})
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            raise ProviderError(f"FxApi fetch failed for {canonical}: {e}") from e

        try:
            rate = float(data["rates"][quote])
            # Frankfurter returns end-of-day rates; use same value for OHLC
            return PriceBar(
                symbol=canonical.upper().replace("/", ""),
                asset_class="forex",
                open=rate,
                high=rate,
                low=rate,
                close=rate,
                volume=None,
                source=self.name,
                fetched_at=datetime.utcnow(),
            )
        except (KeyError, ValueError) as e:
            raise ProviderError(f"FxApi: malformed response for {canonical}: {e}") from e
