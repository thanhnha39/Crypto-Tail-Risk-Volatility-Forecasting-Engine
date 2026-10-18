"""Run Huân's data acquisition, cleaning and descriptive handoff."""
from pathlib import Path
import argparse

from .download import ROOT, download
from .clean import clean
from .report import report
from .audit import audit
from .validate import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/data.toml")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    download(args.config.resolve(), args.workers)
    clean(args.config.resolve())
    audit()
    report()
    validate()


if __name__ == "__main__":
    main()
