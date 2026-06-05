"""Source adapters that discover and fetch scans from external repositories."""

from .base import RemoteFile, Source, UrlListSource
from .figshare import FigshareSource
from .nbtrd import CrawledScan, crawl_study, crawl_to_manifest

__all__ = [
    "RemoteFile",
    "Source",
    "UrlListSource",
    "FigshareSource",
    "CrawledScan",
    "crawl_study",
    "crawl_to_manifest",
]
