"""Script to populate habits_catalog table from Recommendation/habit_catalog.json"""
import json
import sys
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import engine, DATABASE_URL
from models import Base, HabitCatalog
from dotenv import load_dotenv

load_dotenv()

# Map dopamine_level string to integer
DOPAMINE_LEVEL_MAP = {
    "low": 1,
    "medium": 2,
    "high": 3,
}


def load_habit_catalog() -> list:
    """Load habit catalog from JSON file."""
    # Look for habit_catalog.json in backend/RecommendationEngine/
    catalog_path = Path(__file__).resolve().parent / "Recommendation" / "habit_catalog.json"
    
    if not catalog_path.exists():
        raise FileNotFoundError(f"Habit catalog not found at {catalog_path}")
    
    with open(catalog_path, 'r', encoding='utf-8') as f:
        habits = json.load(f)
    
    return habits


def populate_habits_catalog():
    """Populate habits_catalog table from JSON."""
    # Create database engine
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not set. Please set it in .env file.")
    
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Load habits from JSON
        habits = load_habit_catalog()
        
        print(f"Loading {len(habits)} habits from catalog...")
        
        # Clear existing habits (optional - comment out if you want to keep existing)
        # db.query(HabitCatalog).delete()
        # db.commit()
        # print("Cleared existing habits.")
        
        # Insert habits
        inserted_count = 0
        skipped_count = 0
        
        for habit_data in habits:
            json_habit_id = habit_data.get("habit_id")
            
            # Check if habit already exists (by habit_id from JSON)
            existing = None
            if json_habit_id:
                existing = db.query(HabitCatalog).filter(
                    HabitCatalog.habit_id == json_habit_id
                ).first()
            
            if existing:
                skipped_count += 1
                continue
            
            # Map dopamine_level
            dopamine_str = habit_data.get("dopamine_level", "low").lower()
            dopamine_level = DOPAMINE_LEVEL_MAP.get(dopamine_str, 1)
            
            # Create habit record
            # If JSON has habit_id, we'll set it explicitly and update the sequence
            habit_kwargs = {
                "name": habit_data.get("name", ""),
                "description": None,  # JSON doesn't have description field
                "category": habit_data.get("category"),
                "difficulty": habit_data.get("difficulty"),
                "time_required_mins": habit_data.get("time_min"),
                "dopamine_level": dopamine_level,
                "is_indoor": habit_data.get("indoor"),
                "required_device": habit_data.get("required_device", "none"),
                "popularity_score": habit_data.get("popularity_prior"),
            }
            
            # If JSON has habit_id, preserve it
            if json_habit_id:
                habit_kwargs["habit_id"] = json_habit_id
            
            habit = HabitCatalog(**habit_kwargs)
            db.add(habit)
            inserted_count += 1
        
        db.commit()
        
        # Update sequence to be at least as high as the max habit_id
        if inserted_count > 0:
            db.execute(text("SELECT setval('habits_catalog_habit_id_seq', COALESCE((SELECT MAX(habit_id) FROM habits_catalog), 1), true)"))
            db.commit()
        
        print(f"✓ Inserted {inserted_count} habits")
        print(f"✓ Skipped {skipped_count} existing habits")
        print(f"✓ Total habits in catalog: {db.query(HabitCatalog).count()}")
        
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    populate_habits_catalog()

