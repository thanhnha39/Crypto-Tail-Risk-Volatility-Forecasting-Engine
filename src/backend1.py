"""Reproducible real-data Backend 1 pipeline (no paper generation, no default holdout run)."""
from src.features.build_dataset import main as dataset
from src.evaluation.run_baselines import main as baselines
from src.evaluation.aggregate import main as aggregate
from src.features.validate import validate

def main():
    dataset();baselines();validate();aggregate()

if __name__=="__main__": main()
