from utils import *

# ---  Main Data Generation Function ---

def generate_synthetic_dataset(num_users=3, days_per_user=100):
    """
    Generates a synthetic dataset for N users over D days.
    """
    data = []
    start_date = datetime(2024, 1, 1)
    
    for user_id in range(1, num_users + 1):
        
        # 1. Initialize User State
        # Latent trait for "Bad Day Tendency"
        user_bias = np.random.normal(0.0, 0.5) 
        
        # Initialize t-1 values for autoregression
        prev_screen_time = 200
        prev_steps = 6000
        
        for day in range(days_per_user):
            
            # --- 4. Generate Daily Features (Interconnected Logic) ---
            
            # Generate date and weekend flag
            current_date = start_date + timedelta(days=day)
            weekend_flag = 1 if current_date.weekday() >= 5 else 0
            
            # Generate sleep_hours (Autoregressive) [11, 15, 42]
            # Mean sleep is 7.5.
            # Reduced by previous day's screen time (Vicious Cycle).
            # Increased by previous day's steps (Virtuous Cycle).
            sleep_mean = 7.5 - (prev_screen_time / 100.0) + (prev_steps / 5000.0)
            sleep_hours = max(4.0, min(10.0, np.random.normal(sleep_mean, 1.0)))
            
            # Generate steps (Autoregressive) 
            # Mean steps is 6000.
            # Increased by today's sleep (more rested -> more active).
            steps_mean = 6000 + (sleep_hours - 7.5) * 1000
            steps_mean = steps_mean * (0.8 if weekend_flag == 1 else 1.2) # Less structured walking
            steps = int(max(1000, np.random.lognormal(np.log(steps_mean), 0.5)))
            
            # Generate screen_time and unlocks (Autoregressive) [14, 16]
            # Mean screen time is 220 mins.
            # Increased by poor sleep (maladaptive coping).
            # Decreased by high activity.
            screen_mean = 220 - (sleep_hours - 7.5) * 50 - (steps - 6000) / 100
            screen_time_mins = int(max(60, np.random.normal(screen_mean, 60)))
            
            # Unlocks are correlated with screen time but with noise
            unlock_counts = int(max(30, (screen_time_mins / 3) + np.random.normal(0, 20)))

            # Generate wrote_journal_flag (Probabilistic Coping)
            # More likely to journal if sleep was bad (i.e., user feels bad)
            prob_journal = sigmoid((6.5 - sleep_hours) * 0.5) # 0.5 at 6.5h sleep
            wrote_journal_flag = 1 if np.random.rand() < prob_journal else 0

            # Generate NLP Features
            # Probability of a negative emotion depends on sleep and screen time
            prob_neg_emotion = sigmoid((screen_time_mins - 240)/60 - (sleep_hours - 6.5))
            prob_pos_emotion = sigmoid((sleep_hours - 6.5) * 0.6) * 0.4  # more sleep => more positive emotions
            prob_neut_emotion = 1 - (prob_neg_emotion + prob_pos_emotion)
            prob_neut_emotion = max(0.0, min(prob_neut_emotion, 1.0))

            r = np.random.rand()
            if r < prob_neg_emotion:
                dominant_emotion = random.choice(list(NEL))
            elif r < (prob_neg_emotion + prob_pos_emotion):
                dominant_emotion = random.choice(list(PEL))
            else:
                # Choose from neutral emotions
                neutral_emotions = list(Neutral_Emotions)
                dominant_emotion = random.choice(neutral_emotions)

            # If negative emotion, increase chance of 'Organization' entity
            if dominant_emotion in NEL and np.random.rand() < 0.4:
                dominant_entity = 'Organization'
            else:
                dominant_entity = random.choice(ENTITY_TYPES)
                
            # 1. First, generate the *magnitude* (intensity) of the emotion (0 to 1)
            emotion_magnitude = np.random.beta(5, 2 if dominant_emotion not in Neutral_Emotions else 5)
            
            # 2. Create the new -1 to +1 "valenced" score
            emotion_score_valenced = 0.0
            if dominant_emotion in NEL:
                # Negative emotion (e.g., Anger) -> POSITIVE score (bad for user)
                emotion_score_valenced = emotion_magnitude
            elif dominant_emotion in PEL:
                # Positive emotion (e.g., Joy) -> NEGATIVE score (good for user)
                emotion_score_valenced = -emotion_magnitude
            # if neutral, it remains 0.0
            entity_score = np.random.beta(5, 2)
            
            # --- 5. Calculate Final 'label_bad day' ---
            
            # a. Calculate stress scores
            screen_stress = get_screen_stress(screen_time_mins)
            unlock_stress = get_unlock_stress(unlock_counts)
            emotion_stress = get_emotion_stress(
                emotion_score_valenced, 
                dominant_entity, 
                dominant_emotion, 
                NEL
            )
            
            # b. Calculate resilience scores
            activity_resil = get_activity_resilience(steps)
            journal_resil = get_journal_resilience(wrote_journal_flag)
            weekend_resil = get_weekend_resilience(weekend_flag)
            
            # c. Get sleep modulator
            sleep_amp = get_sleep_amplifier(sleep_hours)
            
            # d. Calculate total stress
            total_stress = (screen_stress + unlock_stress + emotion_stress) * sleep_amp
            
            # e. Calculate total resilience
            total_resilience = activity_resil + journal_resil + weekend_resil
            
            # f. Calculate final Bad Day Score (BDS)
            # Scaled by 0.5 to keep sigmoid in a responsive range
            bds = (total_stress - total_resilience + emotion_stress + user_bias) * 0.5
            
            # g. Get final probability
            prob_bad_day = sigmoid(bds - 1.0) # -1.0 to center the prob, making 0s more common
            
            # h. Sample the binary label
            label_bad_day = 1 if np.random.rand() < prob_bad_day else 0

            # Store data
            data.append({
                "user_id": f"user_{user_id}",
                "date": current_date.strftime('%Y-%m-%d'),
                "screen_time_mins": screen_time_mins,
                "unlock_counts": unlock_counts,
                "sleep_hours": round(sleep_hours, 2),
                "steps": steps,
                "dominant_emotion": dominant_emotion,
                "emotion_score": round(emotion_score_valenced, 4),
                "dominant_entity": dominant_entity,
                "dominant_entity_score": round(entity_score, 4),
                "wrote_journal_flag": wrote_journal_flag,
                "weekend_flag": weekend_flag,
                "label_bad_day": label_bad_day
            })
            
            # Update t-1 values for next loop
            prev_screen_time = screen_time_mins
            prev_steps = steps
            
    return pd.DataFrame(data)



# --- 4. Generate and Display Dataset ---
if __name__ == "__main__":
    # Generate 300 rows (3 users, 100 days each)
    synthetic_data = generate_synthetic_dataset(num_users=20, days_per_user=150)
    synthetic_data.to_csv("Synthetic_dataset20002.csv", index=False)
    
    print("--- Generated Synthetic Dataset Sample ---")
    print(synthetic_data.head(20))
    
    print("\n--- Dataset Info ---")
    print(synthetic_data.info())
    
    print("\n--- 'label_bad day' Distribution ---")
    print(synthetic_data['label_bad_day'].value_counts(normalize=True))

    # To analyze the "hidden" relationships, print the correlation matrix
    print("\n--- Correlation Matrix (Key Features) ---")
    key_features = [
        'label_bad_day', 'screen_time_mins', 'unlock_counts', 
        'sleep_hours', 'steps', 'wrote_journal_flag', 'weekend_flag'
    ]
    # Create a 'neg_emotion_score' to make correlation clear
    synthetic_data['neg_emotion_score'] = synthetic_data.apply(
        lambda row: row['emotion_score'] if row['dominant_emotion'] in NEL else 0, axis=1
    )
    key_features.append('neg_emotion_score')
    
    print(synthetic_data[key_features].corr())
