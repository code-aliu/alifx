class AliFxError(Exception):
    pass


class ProviderError(AliFxError):
    """Raised when an external data provider fails."""
    pass


class DataNormalizationError(AliFxError):
    """Raised when incoming data cannot be normalized."""
    pass


class CacheError(AliFxError):
    """Raised on Redis failures."""
    pass
