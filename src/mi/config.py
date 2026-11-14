"""Load the frozen policy/assumption config and expose its hash (recorded in every dossier version)."""
from __future__ import annotations

import hashlib
import json

from mi.paths import CONFIGS


def load_config(path=None, client_inputs=True) -> dict:
    """Policy config; CLIENT-CONFIRMED answers (data/client_inputs/client_inputs.json) are overlaid when present and valid."""
    p = path or CONFIGS / "policy.json"
    cfg = json.loads(open(p, encoding="utf-8").read())
    if client_inputs and path is None:
        from mi.decision.client_inputs import apply, load_answers
        ans = load_answers()
        if ans:
            cfg = apply(cfg, ans)
    return cfg


def config_hash(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16]
