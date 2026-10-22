"""One agreed TOML protocol for data, features and evaluation."""
from pathlib import Path
import hashlib
import json
import tomllib

ROOT = Path(__file__).resolve().parents[2]

def load_config(path=None):
    path = Path(path) if path else ROOT / "config/data.toml"
    if path.suffix != ".toml":
        raise ValueError("Legacy YAML/synthetic settings are retired; use config/data.toml")
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    backend = tomllib.loads((ROOT / "config/backend1.toml").read_text(encoding="utf-8"))
    config["backend1"] = backend
    return config

def protocol_hash(config):
    return hashlib.sha256(json.dumps(config,sort_keys=True,separators=(",", ":")).encode()).hexdigest()
