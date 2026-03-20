import pandas as pd
import numpy as np

NEGATIVE_EMOTIONS = {
    "sadness","grief","anger","fear","nervousness",
    "remorse","disappointment","disgust","annoyance"

}


INPUT_FILE = "backend/forecasting/synthetic_with_risk.csv"
OUTPUT_FILE = "backend/forecasting/forecast_dataset.csv"


def compute_features(window):
    risks = window["risk_score"].values
    sleeps = window["sleep_hours"].values
    screens = window["screen_time_mins"].values
    emotions = window["dominant_emotion"].str.lower().values

    avg_risk = np.mean(risks)
    risk_slope = risks[-1] - risks[0]
    sleep_avg = np.mean(sleeps)
    sleep_var = np.var(sleeps)
    screen_avg = np.mean(screens)
    screen_spike = screens[-1] - screen_avg
    neg_count = sum(1 for e in emotions if e in NEGATIVE_EMOTIONS)

    return [
        avg_risk,
        risk_slope,
        sleep_avg,
        sleep_var,
        screen_avg,
        screen_spike,
        neg_count
    ]


def build_dataset():
    df = pd.read_csv(INPUT_FILE)

    # 🔥 IMPORTANT: sort properly
    df = df.sort_values(by=["user_id", "date"])

    rows = []

    for user_id, user_df in df.groupby("user_id"):

        user_df = user_df.reset_index(drop=True)

        if len(user_df) < 4:
            continue

        for i in range(len(user_df) - 3):

            window = user_df.iloc[i:i+3]
            next_day = user_df.iloc[i+3]

            features = compute_features(window)

            # label
            relapse = 1 if next_day["risk_score"] >= 0.75 else 0

            rows.append(features + [relapse])

    out_df = pd.DataFrame(rows, columns=[
        "avg_risk_3d",
        "risk_slope",
        "sleep_avg_3d",
        "sleep_variance_3d",
        "screen_avg_3d",
        "screen_spike",
        "negative_emotion_count_3d",
        "label"
    ])

    out_df.to_csv(OUTPUT_FILE, index=False)

    print("✅ Forecast dataset created")
    print("Shape:", out_df.shape)
    print("\nLabel distribution:")
    print(out_df["label"].value_counts())


if __name__ == "__main__":
    build_dataset()