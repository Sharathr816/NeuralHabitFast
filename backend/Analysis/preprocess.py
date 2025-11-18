"""
==========================================================================
PART 1: PREPROCESSING (Guidelines 1, 2, 3)
==========================================================================
This file contains all preprocessing, sanity checks, and Feature encoding steps.
Guidelines 1,2,3
"""

import pandas as pd
import joblib

def preprocess_data(df):
    """
    Runs data sanity checks, encoding, and scaling.
    Saves the processed data for training.
    """
    
    # ⚙️ 1. DATA SANITY CHECKS
    print("\n--- ⚙️ 1. Data Sanity Checks ---")
    print(df.info())
    
    # Check for missing values
    print(f"\nMissing values:\n{df.isnull().sum().to_string()}")
    
    # Data leakage: Handled by generative logic and time-series split.
    print("\nData leakage: Will be prevented using a time-series split.")
    
    # Feature balance
    balance = df['label_bad_day'].mean()
    print(f"\nFeature balance: {balance*100:.2f}% are 'Bad Days'.")
    if balance < 0.2 or balance > 0.8:
        print("Note: Dataset is imbalanced. Will use 'scale_pos_weight' in XGBoost.")
        scale_pos_weight = (df['label_bad_day'] == 0).sum() / (df['label_bad_day'] == 1).sum()
    else:
        scale_pos_weight = 1
        
    # ⚙️ 3. CORRELATION SANITY
    print("\n--- ⚙️ 3. Correlation Sanity Check ---")
    print("Correlations with 'label_bad_day':")
    # We use the original 'df' for a simpler numeric-only correlation check
    corr_check = df.corr(numeric_only=True)['label_bad_day'].sort_values()
    print(corr_check.to_string())
    if corr_check['sleep_hours'] > 0 or corr_check['steps'] > 0:
        print("WARNING: Correlation check failed. Check generative logic.")
    else:
        print("Correlation check passed: 'sleep_hours' and 'steps' are negatively correlated with a bad day.")

    # ⚙️ 2. FEATURE ENCODING & SCALING
    print("\n--- ⚙️ 2. Feature Encoding ---")
    
    # Convert date to datetime object for splitting
    df['date'] = pd.to_datetime(df['date'])
    
    # One-hot encode categorical features
    df_processed = pd.get_dummies(df, columns=['dominant_emotion', 'dominant_entity'], drop_first=True)
    print("Encoded 'dominant_emotion' and 'dominant_entity' using one-hot encoding.")
    
    # Define features (X) and target (y)
    y = df_processed['label_bad_day']
    # Drop target, IDs, and date (date is only for splitting)
    X = df_processed.drop(columns=['label_bad_day', 'user_id', 'date'])
    feature_cols = list(X.columns)
    print(f"Final feature columns ({len(feature_cols)}): {feature_cols}")
    
    # Save processed data for other modules
    print("Saving processed data to disk...")
    joblib.dump(X, 'processed_X.joblib')
    joblib.dump(y, 'processed_y.joblib')
    joblib.dump(df_processed, 'processed_df.joblib')
    joblib.dump(scale_pos_weight, 'scale_pos_weight.joblib')
    joblib.dump(feature_cols, "feature_cols.joblib")


    print("Preprocessing complete.")
    return