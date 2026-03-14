"""
==========================================================================
MAIN WORKFLOW RUNNER
==========================================================================
This script executes the entire ML workflow from data generation
to explanation.
"""

import DatasetGen
import preprocess
import Train_XG
import Evaluation
import SHAP
import warnings
import os
import joblib

import pandas as pd

def main():
    """
    Runs the full data generation, preprocessing, training,
    evaluation, and explanation pipeline.
    """
    
    # Suppress warnings for cleaner output
    warnings.filterwarnings('ignore')

    # Step 0: Generate Data
    # print("==========================================")
    # print("STEP 0: GENERATING SYNTHETIC DATASET...")
    # print("==========================================")
    # df = data_generator.generate_synthetic_dataset(num_users=20, days_per_user=150)
    df = pd.read_csv("Synthetic_dataset2000_moderate_realism.csv", parse_dates=["date"])
    # print(f"Dataset generated with {len(df)} rows.")

    #Step 1: Preprocessing (Guidelines 1, 2, 3)
    print("\n==========================================")
    print("STEP 1: PREPROCESSING & SANITY CHECKS...")
    print("==========================================")
    preprocess.preprocess_data(df)

    # Step 2: Model Training (Guidelines 4, 5)
    print("\n==========================================")
    print("STEP 2: TRAINING MODELS...")
    print("==========================================")
    Train_XG.train_models()

    # Step 3: Model Evaluation (Guidelines 5, 7)
    # print("\n==========================================")
    # print("STEP 3: EVALUATING MODELS...")
    # print("==========================================")
    # Evaluation.evaluate_models()

    # # # Step 4: Model Explanation (Guidelines 6, 8, 9)
    # print("\n==========================================")
    # print("STEP 4: EXPLAINING MODEL (SHAP)...")
    # print("==========================================")
    # SHAP.explain_model()

    print("\n==========================================")
    print("--- WORKFLOW COMPLETE ---")
    print("==========================================")

    # # Final Step: Clean up saved files
    # cleanup_files = [
    #     'processed_X.joblib', 'processed_y.joblib', 'processed_df.joblib',
    #     'scale_pos_weight.joblib', 'logreg_model.joblib',
    #     'xgb_model.joblib', 'X_test.joblib', 'y_test.joblib'
    # ]
    # print(f"\nCleaning up intermediate files: {cleanup_files}")
    # for f in cleanup_files:
    #     if os.path.exists(f):
    #         os.remove(f)

if __name__ == "__main__":
    main()