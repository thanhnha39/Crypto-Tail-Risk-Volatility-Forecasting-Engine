from pathlib import Path
import hashlib
import tomllib
from src.utils.config import ROOT

def load_model_config():
    path=ROOT/"config/backend2.toml"
    options=tomllib.loads(path.read_text(encoding="utf-8"))
    validate_model_config(options)
    return options

def validate_model_config(options):
    fixed={"mean":"Constant","distribution":"StudentsT","p":1,"q":1,"power":2.0,"rescale":False,
        "retry_start":"conservative_training_only"}
    for key,value in fixed.items():
        if options["garch"].get(key)!=value:raise ValueError(f"Group protocol requires garch.{key}={value!r}")
    combination=options["combination"]
    if combination["method"]!="equal_weight_variance" or not combination["require_all_components"]:
        raise ValueError("Combination requires equal variance weights and all configured components")
    components=combination["components"]
    if len(components)<2 or len(set(components))!=len(components) or combination["model_name"] in components:
        raise ValueError("Combination needs distinct component names and a separate output model name")
    evaluation=options["evaluation"]
    if evaluation!={"segment":"evaluation","include_expanding_sensitivity":True,"include_seven_day_sensitivity":True}:
        raise ValueError("Default run must preserve the agreed evaluation, expanding and h7 scope")

def model_config_hash():
    return hashlib.sha256((ROOT/"config/backend2.toml").read_bytes()).hexdigest()
