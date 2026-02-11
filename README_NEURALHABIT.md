# NeuralHabit - Complete System Documentation

## Overview

NeuralHabit is a comprehensive habit coaching application that combines:
- **Behavioral Analysis** (XGBoost model) - Analyzes user patterns from journals and mobile data
- **Habit Recommendations** (DeepFM model) - Recommends personalized habits from catalog
- **AI Habit Coach** (LLM-powered) - Provides empathetic coaching with micro-habits and plans

## Architecture

```
┌─────────────────┐
│  Flutter App    │
│   (Frontend)    │
└────────┬────────┘
         │ HTTP/REST
         ▼
┌─────────────────────────────────────────┐
│         FastAPI Backend                 │
│  ┌───────────────────────────────────┐  │
│  │  Authentication & User Management │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │  Journal Ingestion & Analysis     │  │
│  │  - Stores journals in PostgreSQL  │  │
│  │  - Analyzes with XGBoost          │  │
│  │  - Stores results in habit_analysis│ │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │  Habit Coach Service              │  │
│  │  - Vector search (ChromaDB)       │  │
│  │  - LLM coaching (OpenAI/fallback) │  │
│  │  - Recommendation integration     │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │  Recommendation Engine (DeepFM)   │  │
│  │  - Scores habits from catalog     │  │
│  │  - SHAP explanations              │  │
│  └───────────────────────────────────┘  │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│      PostgreSQL Database                │
│  - users                                │
│  - journals                             │
│  - habit_analysis                       │
│  - habits_catalog                       │
│  - recommended_habits                   │
│  - coach_sessions                       │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│      ChromaDB (Vector Store)            │
│  - Journal embeddings for RAG           │
└─────────────────────────────────────────┘
```

## Complete Workflow

### 1. User Registration/Login
- User signs up or logs in via Flutter app
- Credentials stored in `users` table
- Session persisted locally using `shared_preferences`

### 2. Journal Entry Submission
- User writes journal entry in Flutter app
- Optionally provides mobile data:
  - Screen time (minutes)
  - Unlock count
  - Sleep hours
  - Steps (last 24h)
  - Dominant emotion
- Data sent to `/ingest/journal` endpoint
- Journal stored in `journals` table
- Journal text added to ChromaDB vector store
- Analysis triggered in background

### 3. Behavioral Analysis
- Analysis engine processes journal + mobile data
- XGBoost model predicts risk score
- SHAP values extracted for top features
- Results stored in `habit_analysis` table:
  - `risk_score`
  - `prediction_label`
  - `top_features` (JSONB)
  - `raw_shap` (JSONB)

### 4. Habit Coaching Request
- User navigates to "Habit Coach" page
- Frontend calls `/coach/get-coaching?user_id=X`
- Backend:
  1. Retrieves latest analysis for user
  2. Gets relevant journal snippets via vector search
  3. Gets recommended habits from catalog using DeepFM
  4. Constructs prompt with:
     - Top 3 features with impact
     - Dominant emotion + score
     - 3-6 journal snippets
     - Candidate habit titles
  5. Generates coaching via LLM (or fallback)
  6. Saves coaching session to `coach_sessions`
  7. Saves recommendations to `recommended_habits`

### 5. User Views Coaching
- Frontend displays:
  - Empathetic coaching reply (≤140 words)
  - Up to 2 micro-habits with:
    - Title
    - Plan (when & how)
    - Duration
    - Success metric
    - Reasoning
  - Analysis snapshot

## Key Features

### Habit Coach Service
- **Vector Search**: Uses ChromaDB for semantic search of journal entries
- **LLM Integration**: OpenAI GPT-3.5-turbo with deterministic fallback
- **Personalization**: Based on user's latest analysis and journal history
- **Automatic Habit Selection**: Uses recommendation engine to pick best habits

### Recommendation Engine
- **DeepFM Model**: Factorization Machine + Deep Neural Network
- **SHAP Explanations**: Explains why each habit is recommended
- **Catalog Integration**: Automatically loads from `habit_catalog.json`
- **Case-Insensitive**: Handles all input variations gracefully

### Analysis Engine
- **XGBoost Model**: Trained on synthetic behavioral data
- **SHAP Values**: Explains feature importance
- **Automatic Storage**: Results stored in database automatically

## Database Schema

### Tables

1. **users** - User accounts
2. **journals** - Journal entries with mobile data
3. **habit_analysis** - Analysis results (risk scores, SHAP values)
4. **habits_catalog** - Master catalog of available habits
5. **recommended_habits** - User-specific recommendations
6. **coach_sessions** - Coaching responses and context

See `backend/database/schema.sql` for complete schema.

## API Endpoints

### Authentication
- `POST /auth/signup` - Register new user
- `POST /auth/login` - Login user

### Journals
- `POST /ingest/journal` - Submit journal entry
  ```json
  {
    "user_id": 1,
    "text": "Today I felt stressed...",
    "screen_minutes": 300,
    "unlock_count": 50,
    "sleep_hours": 6.5,
    "steps": 8000,
    "dominant_emotion": "stress",
    "dominant_emotion_score": -0.7
  }
  ```

### Habit Coach
- `POST /coach/get-coaching?user_id=1` - Get personalized coaching
  ```json
  {
    "session_id": 123,
    "reply": "I notice you're experiencing...",
    "micro_habits": [
      {
        "title": "Box Breathing (1 Min)",
        "plan": "Do this 1-minute activity in the morning...",
        "duration_minutes": 1,
        "metric": "done_yes_no",
        "why": "This habit addresses screen_time and helps with stress feelings"
      }
    ],
    "evidence": ["snippet 1", "snippet 2"],
    "analysis_snapshot": {
      "risk_score": 0.75,
      "top_features": [...],
      "dominant_emotion": "stress"
    },
    "recommendations_saved": true
  }
  ```

- `GET /coach/sessions/{user_id}?limit=10` - Get coaching history

### Analysis
- `POST /analyse-day?user_id=1&journal_id=123` - Analyze and store results

### Recommendations (Internal)
- `POST /recommend` - Get habit recommendations (used by coach service)

## Running the System

See `backend/RUNNING_GUIDE.md` for detailed setup and running instructions.

### Quick Start

```bash
# 1. Setup database
cd backend
python -c "from database import Base, engine; Base.metadata.create_all(bind=engine)"
python database/populate_habits_catalog.py

# 2. Train recommendation model (first time)
cd RecommendationEngine
python featurize.py
python train_deepfm.py

# 3. Start backend
cd ../backend
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# 4. Start frontend
cd ../frontend
flutter run
```

## Configuration

### Backend (.env)
```env
DATABASE_URL=postgresql://user:pass@localhost:5432/neuralhabit
OPENAI_API_KEY=sk-...  # Optional
EMBED_MODEL=all-MiniLM-L6-v2
```

### Frontend (config.dart)
```dart
const String backendBaseUrl = 'http://10.0.2.2:8000';  // Android emulator
// or 'http://YOUR_IP:8000' for physical device
```

## Network Configuration

- **Android Emulator**: `http://10.0.2.2:8000` (default)
- **Physical Device**: `http://YOUR_PC_IP:8000`
- **iOS Simulator**: `http://localhost:8000`
- **Physical iOS**: `http://YOUR_PC_IP:8000`

## Troubleshooting

### Backend won't start
- Check PostgreSQL is running
- Verify `DATABASE_URL` in `.env`
- Ensure all Python dependencies installed

### Frontend can't connect
- Verify backend is running: `curl http://localhost:8000/`
- Check backend URL in `config.dart`
- For physical device: Use PC's IP, not `localhost`
- Check firewall allows port 8000

### "Failed to featurize" errors
- Ensure recommendation model is trained
- Check `habit_catalog.json` exists
- Verify model files in `RecommendationEngine/models/`

### "No analysis found"
- Submit a journal entry first
- Ensure journal has mobile data (screen_time, etc.)
- Check `habit_analysis` table has entries

## Development Notes

- **Recommendation Engine**: Isolated in `backend/RecommendationEngine/`, not directly connected to frontend
- **Analysis Engine**: Only touched for frontend connection, models/logic unchanged
- **Vector Store**: ChromaDB for RAG-based journal retrieval
- **LLM Fallback**: Deterministic responses when OpenAI API key not available

## Next Steps

1. Add mobile data collection in Flutter (screen time, steps APIs)
2. Implement habit tracking and completion
3. Add user feedback on recommendations
4. Enhance LLM prompts based on user feedback
5. Add analytics and reporting


