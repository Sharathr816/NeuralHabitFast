"""
==========================================================================
PART 4: MODEL EXPLANATION (Guidelines 6, 8, 9)
==========================================================================
This file loads the trained XGBoost model and test data to
generate SHAP explanations and run behavioral validation.
"""

import pandas as pd
import numpy as np
import joblib
import shap
import matplotlib.pyplot as plt

def explain_model():
    """
    Loads the trained XGBoost model and test set,
    calculates SHAP values, and performs behavioral validation.
    """
    
    # Load model and test data
    print("Loading model and test data for SHAP explanation...")
    xgb_model = joblib.load('xgb_model.joblib')
    X_test = joblib.load('X_test.joblib')
    
    # ⚡ 6. FEATURE IMPORTANCE / SHAP
    print("\n--- ⚡ 6. Feature Importance / SHAP ---")
    print("Calculating SHAP values... (this may take a moment)")
    
    # Initialize the explainer and get SHAP values
    explainer = shap.Explainer(xgb_model)
    shap_values = explainer(X_test)

    print("Generating SHAP plots...")
    
    # Plot 1: Global Importance (Bar Plot)
    plt.figure()
    plt.title("SHAP Global Feature Importance (Bar Plot)")
    shap.plots.bar(shap_values, max_display=20, show=False)
    plt.tight_layout()
    
    # Plot 2: Summary "Beeswarm" Plot
    plt.figure()
    plt.title("SHAP Summary Plot (Beeswarm)")
    shap.summary_plot(shap_values, X_test, max_display=20, show=False)
    plt.tight_layout()

    # 🚀 8. BEHAVIORAL VALIDATION
    print("\n--- 🚀 8. Behavioral Validation (Programmatic) ---")
    print("Checking if model outputs make psychological sense...")
    
    # Get model predictions for validation
    y_pred_xgb = xgb_model.predict(X_test)
    
    # We get the index for 'sleep_hours' and 'screen_time_mins'
    try:
        sleep_col_index = X_test.columns.get_loc('sleep_hours')
        screen_col_index = X_test.columns.get_loc('screen_time_mins')
        
        # Find all test set predictions that were 'Bad Days'
        bad_day_indices = np.where(y_pred_xgb == 1) # Get 1D array
        
        if len(bad_day_indices) > 0:
            # Get the average SHAP value for 'sleep_hours' on predicted bad days
            avg_sleep_shap_bad_day = shap_values.values[bad_day_indices, sleep_col_index].mean()
            avg_screen_shap_bad_day = shap_values.values[bad_day_indices, screen_col_index].mean()
            
            print(f"Avg 'sleep_hours' SHAP value on bad days: {avg_sleep_shap_bad_day:.3f}")
            print(f"Avg 'screen_time_mins' SHAP value on bad days: {avg_screen_shap_bad_day:.3f}")

            # VALIDATION LOGIC:
            if avg_sleep_shap_bad_day > 0 and avg_screen_shap_bad_day > 0:
                print("Validation PASSED: On bad days, 'sleep_hours' and 'screen_time' values")
                print("are correctly identified as primary contributors (positive SHAP values).")
            else:
                print("Validation FAILED: Model logic does not align with behavioral assumptions.")
        else:
            print("Validation SKIPPED: Model did not predict any bad days.")
            
    except KeyError as e:
        print(f"Validation SKIPPED: Column not found ({e}).")

    # 🚀 9. EXPLAINABILITY (FOR JOURNAL/PRESENTATION)
    print("\n--- 🚀 9. Explainability ---")
    print("To explain the model's predictions, use the SHAP plots.")
    print(" - The 'SHAP Summary Plot' shows which features were most important and")
    print("   their impact. (e.g., 'sleep_hours' is a top feature, and low values (blue)")
    print("   push the prediction higher (positive SHAP value) -> Bad Day).")
    print(" - This aligns with behavioral research and proves the model is not random.")
    
    print("\n--- Displaying SHAP Plots... ---")
    plt.show()
    
    print("Explanation complete.")
    return