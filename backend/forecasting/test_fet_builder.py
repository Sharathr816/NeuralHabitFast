from ..forecasting.feature_builder import compute_sbii_features

user_id = 14

features = compute_sbii_features(user_id)

print("SBII Features")
print(features)