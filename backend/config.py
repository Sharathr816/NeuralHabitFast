MODELS_DIR = "Analysis"   # folder containing xgb_model.pkl and feature_cols.joblib
MODEL_FILENAME = "xgb_model.joblib"
FEATURE_COLS_FILENAME = "feature_cols.joblib"



from gliner import GLiNER
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline


emotion_labels = [
        "Admiration", "Amusement", "Anger", "Annoyance", "Approval", "Caring", "Confusion",
        "Curiosity", "Desire", "Disappointment", "Disapproval", "Disgust", "Embarrassment",
        "Excitement", "Fear", "Gratitude", "Grief", "Joy", "Love", "Nervousness", "Optimism",
        "Pride", "Realization", "Relief", "Remorse", "Sadness", "Surprise", "Neutral"
    ]

entity_labels = ["person", "Location", "Organization"]


model_name = "codewithdark/bert-Gomotions" #model provides outpus as label:label_17 for joy
bert_tokenizer = AutoTokenizer.from_pretrained(model_name)
emotion_model = AutoModelForSequenceClassification.from_pretrained(model_name)

entity_model = GLiNER.from_pretrained("urchade/gliner_small-v2.1")