# generate_cleaned_v4.py
import os, json
import pandas as pd
import numpy as np

# === CONFIG ===
CSV_IN = "final_clean_dataset.csv"
CATALOG_IN = "habit_catalog_clean.json"
CSV_OUT = "final_clean_dataset_cleaned_v4.csv"

# Emotion lists you gave
EMOTION_LABELS = [
    "Admiration", "Amusement", "Anger", "Annoyance", "Approval", "Caring", "Confusion",
    "Curiosity", "Desire", "Disappointment", "Disapproval", "Disgust", "Embarrassment",
    "Excitement", "Fear", "Gratitude", "Grief", "Joy", "Love", "Nervousness", "Optimism",
    "Pride", "Realization", "Relief", "Remorse", "Sadness", "Surprise", "Neutral"
]

NEL = set([
    "Sadness", "Grief", "Anger", "Fear", "Nervousness", "Remorse", "Disappointment", "Disgust", "Annoyance"
])
PEL = set([
    "Joy", "Excitement", "Gratitude", "Optimism", "Admiration", "Relief", "Pride", "Love"
])
NEUT = set(EMOTION_LABELS) - NEL - PEL

# make mapping from raw strings (lowercased) -> bucket: 'sad','anger','stress','joy','neutral','other'
# We'll map using exact label matches plus some fuzzy contains
NER_TO_BUCKET = {}
for e in NEL:
    NER_TO_BUCKET[e.lower()] = 'neg'
for e in PEL:
    NER_TO_BUCKET[e.lower()] = 'pos'
for e in NEUT:
    NER_TO_BUCKET[e.lower()] = 'neutral'

def bucket_emotion(raw):
    if not isinstance(raw, str):
        return 'other'
    s = raw.strip().lower()
    # exact map
    if s in NER_TO_BUCKET:
        val = NER_TO_BUCKET[s]
        if val == 'neg': return 'sad'   # negative -> treat as 'sad' family (behavioral activation)
        if val == 'pos': return 'joy'
        return 'neutral'
    # fuzzy heuristics
    if any(k in s for k in ['sad','grief','lonely','melancholy']):
        return 'sad'
    if any(k in s for k in ['ang','annoy','frustr','rage','disgust']):
        return 'anger'
    if any(k in s for k in ['anx','nerv','panic','fear','stress','worri']):
        return 'stress'
    if any(k in s for k in ['joy','happy','excite','optimism','grat','pride','love','relief']):
        return 'joy'
    if any(k in s for k in ['neutral','ok','fine','meh']):
        return 'neutral'
    return 'other'

# Load files
if not os.path.exists(CSV_IN):
    raise FileNotFoundError(CSV_IN + " not found. Put it in this folder.")
if not os.path.exists(CATALOG_IN):
    raise FileNotFoundError(CATALOG_IN + " not found.")

df = pd.read_csv(CSV_IN)
with open(CATALOG_IN, 'r', encoding='utf-8') as f:
    catalog = json.load(f)
hab = pd.DataFrame(catalog)

# ensure habit_id ints
hab['habit_id'] = pd.to_numeric(hab['habit_id'], errors='coerce').astype('Int64')
hab_meta_cols = ["habit_id","category","difficulty","time_min","dopamine_level","indoor","required_device","popularity_prior"]
hab_meta = hab[hab_meta_cols].drop_duplicates(subset=['habit_id']).set_index('habit_id')

# filter rows with valid habit_id in catalog
df['habit_id'] = pd.to_numeric(df.get('habit_id', pd.Series([None]*len(df))), errors='coerce').astype('Int64')
initial_rows = len(df)
df = df[df['habit_id'].notna()].copy()
df['habit_id'] = df['habit_id'].astype(int)
valid_ids = set(hab_meta.index.dropna().astype(int).tolist())
df = df[df['habit_id'].isin(valid_ids)].copy()
dropped = initial_rows - len(df)

# Overwrite/attach metadata from catalog (strict mapping)
for c in ['category','difficulty','time_min','dopamine_level','indoor','required_device','popularity_prior']:
    df[c] = df['habit_id'].map(hab_meta[c]).astype(object)

# fill defaults for missing meta
df['difficulty'] = pd.to_numeric(df['difficulty'], errors='coerce').fillna(3).astype(int)
df['time_min'] = pd.to_numeric(df['time_min'], errors='coerce').fillna(5).astype(int)
df['popularity_prior'] = pd.to_numeric(df['popularity_prior'], errors='coerce').fillna(0.5)
df['indoor'] = df['indoor'].fillna(False)

# user side numeric coercion
num_cols = ["risk_score","prediction","emotion_score","screen_time","unlocks","sleep_hours","steps_last_24h"]
for c in num_cols:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(df[c].median())
    else:
        df[c] = 0.0

df['dominant_emotion'] = df.get('dominant_emotion', pd.Series(['unknown']*len(df))).astype(str)
df['emotion_bucket'] = df['dominant_emotion'].apply(bucket_emotion)

# --- FINAL STRONG HEURISTICS FOR LABELS (contrastive) ---
# We'll produce 'heuristic_score' in [0,1] using strong additive rules; then create binary label with flexible threshold + per-emotion balancing.
def strong_heuristic(row):
    # base depends on emotion family
    emo = row['emotion_bucket']
    cat = str(row['category']).lower()
    diff = int(row['difficulty'])
    tmin = int(row['time_min'])
    scr = float(row['screen_time'])
    steps = float(row['steps_last_24h'])
    unlocks = float(row['unlocks']) if 'unlocks' in row else 0.0
    sleep = float(row['sleep_hours'])
    risk = float(row['risk_score'])
    pop = float(row.get('popularity_prior', 0.5))
    s = 0.0

    # SAD family => behavioral activation (physical micro tasks preferred)
    if emo == 'sad':
        if cat == 'physical' and diff <= 2 and tmin <= 15:
            s += 0.6
        if cat in ['mental','spiritual'] and diff <= 2 and tmin <= 10:
            s += 0.35
        # punitive for high-effort physical
        if cat == 'physical' and diff >= 4:
            s -= 0.4

    # STRESS => grounding & breathing
    elif emo == 'stress':
        if cat in ['mental','spiritual'] and tmin <= 5:
            s += 0.6
        if cat == 'physical' and tmin <= 5:
            s += 0.2

    # ANGER => quick grounding + physical safe output
    elif emo == 'anger':
        if cat in ['mental','spiritual'] and tmin <= 5:
            s += 0.45
        if cat == 'physical' and tmin <= 10:
            s += 0.35

    # JOY => higher-dopamine physical & phone-friendly if phone available
    elif emo == 'joy':
        if cat == 'physical' and diff >= 2 and tmin <= 30:
            s += 0.55
        if str(row.get('required_device','')).lower() == 'phone' and pop > 0.6 and unlocks < 100:
            s += 0.25

    # NEUTRAL / OTHER => low bias, prefer low-cost micro tasks (mixed)
    else:
        if cat == 'physical' and tmin <= 10:
            s += 0.25
        if cat in ['mental','spiritual'] and tmin <= 10:
            s += 0.25

    # behavior signals adjustments
    if scr >= 180 or steps < 3000:
        # high screen or sedentary -> boost micro physicals
        if cat == 'physical' and tmin <= 10:
            s += 0.25
    if sleep >= 8 and steps < 4000:
        if cat == 'physical' and diff <= 2 and tmin <= 15:
            s += 0.2

    # safety guardrail
    if risk >= 0.7 and diff >= 4:
        s -= 0.6

    # reduce popularity influence (very small linear boost)
    s += 0.02 * (pop - 0.5)

    # clamp
    return max(0.0, min(1.0, s))

df['heuristic_score'] = df.apply(strong_heuristic, axis=1)

# Build balanced binary label BUT per-emotion thresholds (makes it contrastive)
# We'll set thresholds so that each emotion gets a reasonable positive rate:
# sad/stress/anger => threshold 0.4; joy => 0.45; neutral/other => 0.5
def per_emotion_label(r):
    emo = r['emotion_bucket']
    s = r['heuristic_score']
    if emo in ['sad','stress','anger']:
        return int(s >= 0.40)
    if emo == 'joy':
        return int(s >= 0.45)
    return int(s >= 0.50)

df['label'] = df.apply(per_emotion_label, axis=1)

# Now do a balancing step (optional): if + class is too rare for some emotion, lower threshold for that emo.
# We'll ensure at least 20% positives per emotion bucket if possible by relaxing threshold in scarcity cases.
min_pos_ratio = 0.20
for emo in df['emotion_bucket'].unique():
    sub = df[df['emotion_bucket'] == emo]
    if len(sub) == 0:
        continue
    pos_ratio = sub['label'].mean()
    if pos_ratio < min_pos_ratio:
        # find value to target ~20%
        scores = np.sort(sub['heuristic_score'].values)
        if len(scores) > 0:
            # new threshold = quantile at (1 - min_pos_ratio)
            new_thr = np.quantile(scores, 1 - min_pos_ratio)
            df.loc[df['emotion_bucket'] == emo, 'label'] = (df.loc[df['emotion_bucket'] == emo, 'heuristic_score'] >= new_thr).astype(int)

# final columns exactly as requested
final_cols = ["risk_score","prediction","dominant_emotion","emotion_score","screen_time","unlocks",
              "sleep_hours","steps_last_24h","habit_id","category","difficulty","time_min",
              "dopamine_level","indoor","required_device","popularity_prior","label"]

for c in final_cols:
    if c not in df.columns:
        # create default if missing
        if c in ['risk_score','prediction','emotion_score','screen_time','unlocks','sleep_hours','steps_last_24h','popularity_prior']:
            df[c] = 0.0
        else:
            df[c] = 'unknown'

df_final = df[final_cols].copy()
df_final.to_csv(CSV_OUT, index=False)
print("WROTE:", CSV_OUT)
print("rows:", len(df_final), "dropped:", dropped)
print("label distribution overall:\n", df_final['label'].value_counts(normalize=False).to_dict())
print("label distribution by emotion:\n", df.groupby('emotion_bucket')['label'].mean().to_dict())
