"""Run this submission against an existing Data–Backend 3 repository without copying data."""
import argparse
from pathlib import Path
import sys

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root',type=Path,required=True,help='Repository containing dataset, config and forecasts')
    parser.add_argument('--skip-strategy',action='store_true')
    parser.add_argument('--test',action='store_true',help='Run Backend 4 tests only')
    args=parser.parse_args()
    root=args.input_root.resolve();submission=Path(__file__).resolve().parent
    if not (root/'src/utils/config.py').is_file():parser.error('input-root must point to the full project repository')
    sys.path.insert(0,str(root))
    import src
    src.__path__.insert(0,str(submission/'src'))
    if args.test:
        import unittest
        suite=unittest.defaultTestLoader.discover(str(submission/'tests'),pattern='test_backend4*.py')
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        raise SystemExit(0 if result.wasSuccessful() else 1)
    from src.risk.run import run
    risks=run(root,submission,not args.skip_strategy)
    print(f'Completed: {len(risks)} scheduled risk rows. Outputs: {submission / "outputs/risk"}')

if __name__=='__main__':main()
