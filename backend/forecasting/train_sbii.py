import os
import joblib
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    roc_auc_score,
    confusion_matrix,
    classification_report
)

# =============================
# PATHS
# =============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_PATH = os.path.join(BASE_DIR, "forecasting", "forecast_dataset.csv")
MODEL_PATH = os.path.join(BASE_DIR, "forecasting", "sbii_model.pkl")

# =============================
# LOAD DATA
# =============================
df = pd.read_csv(DATA_PATH)

print("Dataset Loaded:", df.shape)

# =============================
# SPLIT FEATURES & LABEL
# =============================
X = df.drop(columns=["label"])
y = df["label"]

# =============================
# TRAIN TEST SPLIT
# =============================
X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

print("Train size:", X_train.shape)
print("Test size:", X_test.shape)

# =============================
# MODEL (Logistic Regression)
# =============================
model = LogisticRegression(max_iter=1000)

# Train
model.fit(X_train, y_train)

# =============================
# PREDICTIONS
# =============================
# 0.5 threshold for binary classification
y_pred = model.predict(X_test)  
y_prob = model.predict_proba(X_test)[:, 1]

# try different threshold and check
# threshold = 0.5
# y_pred = (y_prob >= threshold).astype(int)

# =============================
# EVALUATION
# =============================
accuracy = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred)
recall = recall_score(y_test, y_pred)
roc_auc = roc_auc_score(y_test, y_prob)

cm = confusion_matrix(y_test, y_pred)

print("\n===== MODEL METRICS =====")
print(f"Accuracy   : {accuracy:.4f}")
print(f"Precision  : {precision:.4f}")
print(f"Recall     : {recall:.4f}")
print(f"ROC-AUC    : {roc_auc:.4f}")

print("\n===== CONFUSION MATRIX =====")
print(cm)

print("\n===== CLASSIFICATION REPORT =====")
print(classification_report(y_test, y_pred))

# =============================
# SAVE MODEL
# =============================
joblib.dump(model, MODEL_PATH)

print(f"\n✅ Model saved at: {MODEL_PATH}")