# NeuralHabit

## 🚀 Project Overview

**NeuralHabit** is an AI-powered habit analysis and recommendation app.It helps **students and people striving for growth** to build and keep habits by reducing stress, overcoming digital overload, and planning better.

The app combines **journaling (text/voice)**, **behavior analysis**, **habit tracking**, and an **empathetic AI coach** to guide users in their daily routines.

## 🧑‍🤝‍🧑 Target Users

* Mainly **students** and self-improvers.



## ✨ Core Features

1. **Journaling (text + voice)**

   * Voice input → converted to text (Whisper).
   * Journals analyzed for **sentiment, entities, keywords** (DistilBERT).

2. **Analysis Engine**

   * Detects stress patterns, recurring issues, and links between activities.
   * Models: XGBoost/LSTM(later stages).

3. **Recommendation Engine**

   * Suggests positive habits based on journal + streaks using DeepFM.
   * Explains *why* the habit was recommended (SHAP interpretability).

4. **Gamification**

   * Habits as buttons in the app (positive/negative).
   * Completing positive = XP gain, negative = HP loss.
   * Simple game loop to motivate consistency.

5. **Habit Coach (Chatbot)**

   * GPT-based, empathetic, context-aware coach.
   * Uses user journals, habits, and calendar to guide behavior.

6. **Calendar Integration**

   * Syncs with Google Calendar.
   * Detects overload (too many meetings/events).



## 🛠️ Tech Stack

* **Frontend**: Flutter
* **Backend**: FastAPI (Python)
* **Database**: PostgreSQL + S3
* **AI Models**:

  * Whisper → speech-to-text
  * DistilBERT → sentiment \& entity extraction
  * XGBoost / LSTM  → pattern detection
  * DeepFM → recommendations (later stages)
  * GPT-RAG → empathetic chatbot
