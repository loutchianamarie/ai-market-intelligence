"""Load the frozen policy/assumption config and expose its hash (recorded in every dossier version)."""
from __future__ import annotations

import hashlib
import json

from mi.paths import CONFIGS


def load_config(path=None) -> dict:
    p = path or CONFIGS / "policy.json"
    return json.loads(open(p, encoding="utf-8").read())


def config_hash(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16]
