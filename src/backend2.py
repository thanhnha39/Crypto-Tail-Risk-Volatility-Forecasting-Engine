"""Execute econometric Backend 2 and refresh numerical comparisons; no chapter generation."""
import sys
from src.models.run import main as models
from src.evaluation.aggregate import main as aggregate
from src.models.diagnostics import main as diagnostics

def main():
    models()
    args=["--final-holdout"] if "--final-holdout" in sys.argv else []
    aggregate(args);diagnostics(args)

if __name__=="__main__":main()
