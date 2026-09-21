"""Code-owned public sources that may inspire global quiz generation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PublicContextSourceDefinition:
    """One exact HTTPS document; administrators cannot supply arbitrary URLs."""

    key: str
    url: str
    hostname: str


PUBLIC_CONTEXT_SOURCES = (
    PublicContextSourceDefinition(
        "un-observances",
        "https://www.un.org/en/observances",
        "www.un.org",
    ),
    PublicContextSourceDefinition(
        "nasa-skywatching",
        "https://science.nasa.gov/skywatching",
        "science.nasa.gov",
    ),
    PublicContextSourceDefinition(
        "loc-collections",
        "https://www.loc.gov/collections",
        "www.loc.gov",
    ),
    PublicContextSourceDefinition(
        "smithsonian-spotlight",
        "https://www.si.edu/spotlight",
        "www.si.edu",
    ),
)

PUBLIC_CONTEXT_BY_KEY = {item.key: item for item in PUBLIC_CONTEXT_SOURCES}
PUBLIC_CONTEXT_BY_URL = {item.url: item for item in PUBLIC_CONTEXT_SOURCES}
