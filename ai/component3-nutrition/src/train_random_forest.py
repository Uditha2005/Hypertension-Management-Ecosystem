"""Train/evaluate Random Forest across the three research feature sets."""
import argparse
from model_research import run_model_experiment

def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    cv, test = run_model_experiment('random_forest')
    print(cv[["feature_set_label", "cv_macro_f1_mean", "cv_macro_f1_std"]].to_string(index=False))
    print("\nHeld-out test results:\n", test[test.group == "all_adults"][
        ["feature_set_label", "accuracy", "macro_f1", "weighted_f1"]
    ].to_string(index=False))

if __name__ == "__main__":
    main()
