"""
==========================================================================
PART 3: MODEL EVALUATION (Guidelines 5, 7)
==========================================================================
This file loads the trained models and test data to run
evaluation metrics and cross-validation.
"""

import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import classification_report
from sklearn.model_selection import TimeSeriesSplit, cross_val_score

def evaluate_models():
    """
    Loads trained models and test data, then prints
    classification reports and cross-validation scores.
    """
    
    # Load models and data
    print("Loading models and data for evaluation...")
    logreg_model = joblib.load('logreg_model.joblib')
    xgb_model = joblib.load('xgb_model.joblib')
    X_train = joblib.load('X_train_full.joblib')
    y_train = joblib.load('y_train_full.joblib')
    X_test = joblib.load('X_test.joblib')
    y_test = joblib.load('y_test.joblib')
    
    # ⚡ 5. BASELINE MODELS (EVALUATION)
    print("\n--- ⚡ 5. Baseline Models (Evaluation) ---")
    
    # --- Baseline 1: Logistic Regression ---
    y_pred_logreg = logreg_model.predict(X_test)
    print("\nLogistic Regression - Classification Report (Test Set):")
    print(classification_report(y_test, y_pred_logreg))

    # --- Baseline 2: XGBoost (Primary Model) ---
    y_pred_xgb = xgb_model.predict(X_test)
    print("\nXGBoost - Classification Report (Test Set):")
    print(classification_report(y_test, y_pred_xgb))

    # ⚡ 7. CROSS-VALIDATION
    print("\n--- ⚡ 7. Cross-Validation ---")
    print("Running 5-Fold Time-Series Cross-Validation on XGBoost...")
    # We MUST use a time-series split for CV to prevent leakage
    tscv = TimeSeriesSplit(n_splits=5)
    
    # We use the full (uns-split) X and y, as tscv handles the splits correctly
    cv_scores = cross_val_score(
        xgb_model, X_train, y_train, 
        cv=tscv, 
        scoring='f1_weighted' # Use weighted F1 due to imbalance
    )
    
    print(f"Weighted F1 Scores for each fold: {np.round(cv_scores, 3)}")
    print(f"Average CV Weighted F1: {cv_scores.mean():.3f} +/- {cv_scores.std():.3f}")
    
    print("Evaluation complete.")
    return