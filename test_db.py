import pandas as pd
from datetime import datetime
from database import save_to_supabase

def test_connection():
    print("Testing Supabase Connection...")
    
    # Create dummy data
    dummy_top_100 = pd.DataFrame({
        'Price': [150.0, 2800.0],
        'Turnover': [1000000.0, 5000000.0],
        'Ranking': [1, 2],
        'Avg_Ranking_10d': [5, 10],
        'Rel_Volume': [1.5, 2.0]
    }, index=['AAPL', 'GOOGL'])
    
    dummy_signals = pd.DataFrame({
        'Price': [150.0],
        'Turnover': [1000000.0],
        'Ranking': [1],
        'Avg_Ranking_10d': [5],
        'Rel_Volume': [1.5]
    }, index=['AAPL'])
    
    today = datetime.now().date()
    
    print(f"Attempting to save test data for {today}...")
    save_to_supabase(today, dummy_top_100, dummy_signals)

if __name__ == "__main__":
    test_connection()
