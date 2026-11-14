"""Central paths. Everything is relative to the repository root so the pipeline is reproducible."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
SOURCES = DATA / "sources"
SEO = DATA / "seo"
CONFIGS = ROOT / "configs"
REPORTS = ROOT / "reports"
DOCS = ROOT / "docs"
DB_PATH = DATA / "processed" / "dossier.sqlite"

for _p in (RAW, PROCESSED, REPORTS):
    _p.mkdir(parents=True, exist_ok=True)
