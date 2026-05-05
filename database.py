import os
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

def save_to_supabase(date, top_100, signals):
    """
    Saves the analysis results to a Supabase PostgreSQL database.
    Requires SUPABASE_DB_URL environment variable.
    """
    db_url = os.environ.get("SUPABASE_DB_URL")
    
    if not db_url:
        print("\n[!] Skipping Database Save: SUPABASE_DB_URL environment variable not set.")
        print("    Set it with: $env:SUPABASE_DB_URL='your_connection_string'")
        return

    try:
        from sqlalchemy import create_engine
        engine = create_engine(db_url)

        # Helper to prepare data for SQL
        def prepare_df(df, is_signal):
            if df.empty: return pd.DataFrame()
            temp = df.copy().reset_index()
            # Standardize column names for SQL (lower case, underscores)
            temp.columns = [c.lower().replace(' ', '_').replace('(m)', '_m') for c in temp.columns]
            
            # Explicitly rename columns to match the Supabase schema
            rename_map = {
                'index': 'ticker',
                'turnover': 'turnover_m'
            }
            temp.rename(columns=rename_map, inplace=True)
            
            temp['date'] = date
            temp['is_signal'] = is_signal
            return temp

        # 1. Prepare Top 100
        df_final = prepare_df(top_100, False)
        
        # 2. Mark signals and add any signals not in Top 100
        if not signals.empty:
            signal_tickers = signals.index.tolist()
            # Set is_signal=True for matching tickers in Top 100
            df_final.loc[df_final['ticker'].isin(signal_tickers), 'is_signal'] = True
            
            # Find signals that AREN'T in the Top 100 (to be safe)
            extra_signals = signals[~signals.index.isin(top_100.index)]
            if not extra_signals.empty:
                df_extra = prepare_df(extra_signals, True)
                df_final = pd.concat([df_final, df_extra])

        # 3. Final cleanup and save
        to_save = df_final.drop_duplicates(subset=['date', 'ticker'], keep='last')
        
        if not to_save.empty:
            to_save.to_sql('stock_results', engine, if_exists='append', index=False)
            print(f"\n[+] Successfully saved {len(to_save)} records to Supabase.")
    except Exception as e:
        print(f"\n[!] Error saving to database: {e}")

def get_from_supabase(date):
    """
    Retrieves existing analysis results for a specific date from Supabase.
    Returns (top_100, signals) DataFrames, or (None, None) if not found.
    """
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        return None, None

    try:
        from sqlalchemy import create_engine
        engine = create_engine(db_url)
        
        # 1. Fetch data for the date
        query = f"SELECT * FROM stock_results WHERE date = '{date}'"
        df = pd.read_sql(query, engine)

        if df.empty:
            return None, None

        # 2. Transform back to the script's expected format
        df.set_index('ticker', inplace=True)
        rename_map = {
            'price': 'Price',
            'turnover_m': 'Turnover',
            'ranking': 'Ranking',
            'avg_ranking_10d': 'Avg_Ranking_10d',
            'rel_volume': 'Rel_Volume'
        }
        df.rename(columns=rename_map, inplace=True)
        
        # 3. Separate the data
        top_100 = df.drop(columns=['id', 'date', 'created_at', 'is_signal'], errors='ignore')
        signals = df[df['is_signal'] == True].drop(columns=['id', 'date', 'created_at', 'is_signal'], errors='ignore')
        
        print(f"[+] Retrieved cached results for {date} from Supabase.")
        return top_100, signals

    except Exception as e:
        print(f"[!] Error fetching from database: {e}")
        return None, None
