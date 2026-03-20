import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
    
# --- 1. Define Feature Lists (Based on User Query) ---

# Based on "codewithdark/bert-Gomotions"
EMOTION_LABELS = [
    "Admiration", "Amusement", "Anger", "Annoyance", "Approval", "Caring", "Confusion",
    "Curiosity", "Desire", "Disappointment", "Disapproval", "Disgust", "Embarrassment",
    "Excitement", "Fear", "Gratitude", "Grief", "Joy", "Love", "Nervousness", "Optimism",
    "Pride", "Realization", "Relief", "Remorse", "Sadness", "Surprise", "Neutral"
]

# Negative and Positive valence lists for modeling
NEL = [
    "Sadness", "Grief", "Anger", "Fear", "Nervousness", "Remorse", "Disappointment", "Disgust", "Annoyance", "Confusion"
]
PEL = [
    "Joy", "Excitement", "Gratitude", "Optimism", "Admiration", "Relief", "Pride", "Love", "Amusement", "Approval", "Caring", "Curiosity", "Realization", "Surprise"
]
Neutral_Emotions = set(EMOTION_LABELS) - set(NEL) - set(PEL)

# Based on "urchade/gliner_small-v2.1"
ENTITY_TYPES = ["person", "Location", "Organization"]

# --- 2. Define Helper Functions (Based on Part 2 Formulation) ---

def sigmoid(x):
    """Logistic sigmoid function for probabilities."""
    return 1 / (1 + np.exp(-x))

def get_screen_stress(mins):
    """Calculates stress score based on screen time. """
    if mins < 240:
        return 0.0
    elif 240 <= mins < 360:
        return 1.3
    else:
        return 1.8

def get_unlock_stress(count):
    """Calculates stress score from high unlock frequency. """
    return max(0.0, (count - 100) * 0.02)

def get_sleep_amplifier(hours):
    """Calculates stress multiplier from sleep. [10, 12, 23]"""
    # 8.0 / 4.5 = 1.77, matching the 4.5-hour threshold finding.
    # Capped at 4.0 hours to prevent extreme values.
    return 8.0 / max(hours, 4.0)

def get_activity_resilience(steps):
    """Calculates resilience score from steps. """
    if steps < 3000:
        return 0.0
    elif 3000 <= steps < 7000:
        return 1.0  # Approaching 7k threshold
    elif 7000 <= steps < 10000:
        return 1.5  # 31% risk reduction at 7k 
    else:
        return 2.0  # 10k+ steps 

def get_journal_resilience(flag):
    """Calculates resilience from journaling. """
    return 1.0 if flag == 1 else 0.0

def get_weekend_resilience(flag):
    """Calculates baseline resilience from weekend. """
    return 1.0 if flag == 1 else 0.0

def get_emotion_stress(emotion_score_valenced, dominant_entity, dominant_emotion, NEL):
    """
    Calculates the final stress contribution from the new -1 to +1 emotion score.
    """
    # 'emotion_score_valenced' is the new score from -1 (very positive) to +1 (very negative).
    # A positive score adds stress, a negative score adds resilience.
    
    base_stress = emotion_score_valenced
    
    # Apply entity amplifier (Rational Assumption for work stress)
    # We only amplify *negative* emotions (which are now scores > 0)
    entity_amplifier = 1.0
    if base_stress > 0 and dominant_emotion in NEL and dominant_entity == 'Organization':
        entity_amplifier = 1.2
    
    # Apply a weight to make emotion a powerful predictor (matches old logic)
    # and apply the amplifier.
    return (base_stress * 1.3) * entity_amplifier
    
    