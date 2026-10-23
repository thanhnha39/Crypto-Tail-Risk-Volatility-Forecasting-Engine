"""ML forecasts, numerical comparison, SHAP and volume ablation; no academic chapters."""
import sys
from src.models.run_ml import main as models
from src.evaluation.aggregate import main as aggregate
from src.models.ml_analysis import main as analysis
from src.evaluation.robustness import main as robustness


def main():
    models()
    args = ["--final-holdout"] if "--final-holdout" in sys.argv else []
    aggregate(args)
    analysis(args)
    if not args:
        robustness()


if __name__ == "__main__":
    main()
