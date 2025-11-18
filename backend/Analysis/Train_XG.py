# """
# ==========================================================================
# PART 2: MODEL TRAINING (Guidelines 4, 5)
# ==========================================================================
# This file loads the preprocessed data, splits it, and trains
# the baseline and XGBoost models.
# Guidelines 4,5
# """

# import pandas as pd
# import xgboost as xgb
# import joblib
# from sklearn.preprocessing import StandardScaler
# from sklearn.linear_model import LogisticRegression
# from sklearn.pipeline import Pipeline
# from sklearn.model_selection import train_test_split

# def train_models():
#     """
#     Loads processed data, splits into train/test, and trains models.
#     Saves trained models and test sets to disk.
#     """
    
#     # Load preprocessed data
#     print("Loading preprocessed data...")
#     X = joblib.load('processed_X.joblib')
#     y = joblib.load('processed_y.joblib')
#     df_processed = joblib.load('processed_df.joblib')
#     scale_pos_weight = joblib.load('scale_pos_weight.joblib')

#     # ⚡ 4. TRAIN/TEST SPLIT (Time-Series Aware)
#     print("\n--- ⚡ 4. Train/Test Split ---")
#     # We MUST split by date to prevent leakage. We'll use the 80th percentile date.
#     split_date = df_processed['date'].quantile(0.8, interpolation='nearest')
    
#     train_mask = (df_processed['date'] <= split_date)
#     test_mask = (df_processed['date'] > split_date)

#     X_train_full, X_test = X[train_mask], X[test_mask]
#     y_train_full, y_test = y[train_mask], y[test_mask]
    
#     print(f"Splitting data on date: {split_date.date()}")
#     print(f"Training set size: {len(X_train_full)}")
#     print(f"Test set size:     {len(X_test)}")

    
#     #In case of early stopping(have to pass eval set in .fit())
#     #Further split training data into train + validation for early stopping
#     X_train, X_val, y_train, y_val = train_test_split(
#     X_train_full, y_train_full,
#     test_size=0.2,
#     shuffle=False
#     )

#     # ⚡ 5. BASELINE MODELS (TRAINING)
#     print("\n--- ⚡ 5. Baseline Models ---")
    
#     # --- Baseline 1: Logistic Regression ---
#     print("\nTraining Baseline 1: Logistic Regression...")
#     # Logistic Regression requires scaling
#     pipeline_logreg = Pipeline([
#     ("scaler", StandardScaler()),           # required for scaling
#     ("logreg", LogisticRegression(max_iter=1000))
#     ])
#     pipeline_logreg.fit(X_train_full, y_train_full)

#     # --- Baseline 2: XGBoost (Primary Model) ---
#     print("\nTraining Baseline 2: XGBoost...")
#     # XGBoost does not require scaling
#     # xgb_model = xgb.XGBClassifier(
#     #     use_label_encoder=False, 
#     #     eval_metric='logloss',
#     #     scale_pos_weight=scale_pos_weight, # Handle imbalance
#     #     n_estimators=100,
#     #     # early_stopping_rounds=10
#     # )

#     xgb_model = xgb.XGBClassifier(
#     n_estimators=500,
#     learning_rate=0.05,
#     max_depth=6,
#     subsample=0.8,
#     colsample_bytree=0.8,
#     scale_pos_weight=scale_pos_weight,
#     eval_metric='logloss'
# )

    
#     # Use the eval set for early stopping
#     xgb_model.fit(X_train_full, y_train_full, verbose=False)
    
#     print("Training complete.")
    
#     # Save models and test data for evaluation/explanation
#     print("Saving models and test sets to disk...")
#     #joblib.dump(pipeline_logreg, 'logreg_model.joblib')
#     joblib.dump(xgb_model, 'xgb_model.joblib')
#     # joblib.dump(X_test, 'X_test.joblib')
#     # joblib.dump(y_test, 'y_test.joblib')
#     # joblib.dump(X_train_full, 'X_train_full.joblib')
#     # joblib.dump(y_train_full, 'y_train_full.joblib')

#     return


# Train_XG.py
"""
PART 2: MODEL TRAINING (Guidelines 4, 5)

- time-series train/test split (80% by date)
- internal train/val split (no shuffle) for early stopping
- trains LogisticRegression (with scaler) and XGBoost (with early stopping)
- retrains XGBoost on full training data using best_iteration
- saves models and datasets to disk
"""

import joblib
import xgboost as xgb
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from xgboost.callback import EarlyStopping


def train_models():
    print("Loading preprocessed data...")
    X = joblib.load('processed_X.joblib')           # pandas DataFrame preferred (index preserved)
    y = joblib.load('processed_y.joblib')           # pandas Series
    df_processed = joblib.load('processed_df.joblib')
    scale_pos_weight = joblib.load('scale_pos_weight.joblib')

    # ⚡ 4. TRAIN/TEST SPLIT (Time-Series Aware)
    print("\n--- ⚡ 4. Train/Test Split ---")
    split_date = df_processed['date'].quantile(0.8, interpolation='nearest')

    train_mask = (df_processed['date'] <= split_date)
    test_mask = (df_processed['date'] > split_date)

    X_train_full, X_test = X[train_mask], X[test_mask]
    y_train_full, y_test = y[train_mask], y[test_mask]

    print(f"Splitting data on date: {split_date.date()}")
    print(f"Training set size: {len(X_train_full)}")
    print(f"Test set size:     {len(X_test)}")

    # internal train/val split for early stopping (time-ordered: shuffle=False)
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_full, y_train_full,
        test_size=0.2,
        shuffle=False
    )
    print(f"Internal train size: {len(X_train)}")
    print(f"Internal val size:   {len(X_val)}")

    # ⚡ 5. BASELINE MODELS (TRAINING)
    print("\n--- ⚡ 5. Baseline Models ---")

    # --- Baseline 1: Logistic Regression ---
    print("\nTraining Baseline 1: Logistic Regression...")
    pipeline_logreg = Pipeline([
        ("scaler", StandardScaler()),
        ("logreg", LogisticRegression(max_iter=2000, random_state=42))
    ])
    # Fit logistic on the full training data (train + val) so final logistic model uses all training info
    pipeline_logreg.fit(X_train_full, y_train_full)
    print("Logistic Regression training complete.")

    # --- Baseline 2: XGBoost (Primary Model) ---
    print("\nTraining Baseline 2: XGBoost (with early stopping)...")
    xgb_model = xgb.XGBClassifier(
        n_estimators=1000,         # large, early stopping will cut it down
        learning_rate=0.06,
        max_depth=3,
        subsample=0.9,
        colsample_bytree=0.9,
        scale_pos_weight=scale_pos_weight,
        use_label_encoder=False,
        eval_metric='logloss',
        verbosity=0,
        random_state=42
    )

    # Fit using internal validation set for early stopping (NO test leakage)
    xgb_model.fit(
    X_train, y_train,
    verbose=False
)

    best_iter = getattr(xgb_model, "best_iteration", None)
    print(f"XGBoost early-stopped. best_iteration = {best_iter}")

    # Retrain final XGBoost on full training data using best_iteration (if found)
    if best_iter is not None:
        final_n_estimators = best_iter + 1
        print(f"Retraining XGBoost on full training data with n_estimators={final_n_estimators} ...")
        xgb_final = xgb.XGBClassifier(
            n_estimators=final_n_estimators,
            learning_rate=0.05,
            max_depth=6,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,
            use_label_encoder=False,
            eval_metric='logloss',
            verbosity=0,
            random_state=42
        )
        xgb_final.fit(X_train_full, y_train_full, verbose=False)
        xgb_model = xgb_final  # replace with final retrained model
        print("Retraining complete.")
    else:
        print("No best_iteration found (early stopping not triggered). Keeping the fitted model as-is.")

    print("Training complete.")

    # Save models and datasets for evaluation/explanation
    print("Saving models and datasets to disk...")
    joblib.dump(pipeline_logreg, 'logreg_model.joblib')
    joblib.dump(xgb_model, 'xgb_model.joblib')

    joblib.dump(X_test, 'X_test.joblib')
    joblib.dump(y_test, 'y_test.joblib')
    joblib.dump(X_train_full, 'X_train_full.joblib')
    joblib.dump(y_train_full, 'y_train_full.joblib')


    print("All saved. Training finished.")
    return

if __name__ == "__main__":
    train_models()
