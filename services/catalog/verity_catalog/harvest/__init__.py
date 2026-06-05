"""Source adapters that discover and fetch scans from external repositories."""

from .base import RemoteFile, Source, UrlListSource
from .figshare import FigshareSource

__all__ = ["RemoteFile", "Source", "UrlListSource", "FigshareSource"]
