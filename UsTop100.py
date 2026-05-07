import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
import time
import os
import pytz
from database import save_to_supabase, get_from_supabase
from email_utils import send_email_report

def get_nasdaq_nyse_tickers():
    """Fetches current NYSE and NASDAQ tickers, excluding OTC."""
    # Using a reliable public CSV source for NASDAQ and NYSE
    nasdaq_url = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/nasdaq/nasdaq_tickers.txt"
    nyse_url = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/nyse/nyse_tickers.txt"
    
    try:
        nasdaq_series = pd.read_csv(nasdaq_url, header=None)[0]
        nyse_series = pd.read_csv(nyse_url, header=None)[0]
        
        nasdaq = [str(t).strip().upper() for t in nasdaq_series.dropna()]
        nyse = [str(t).strip().upper() for t in nyse_series.dropna()]
        
        tickers = sorted(list(set(nasdaq + nyse)))
        return [t for t in tickers if t.isalpha()]
    except Exception as e:
        print(f"Error fetching tickers: {e}")
        return []

def analyze_stocks(target_date_str=None, ticker_limit=None):
    # 1. Setup Dates
    if target_date_str:
        target_date = pd.to_datetime(target_date_str)
    else:
        target_date = datetime.now(pytz.timezone('US/Eastern'))
    
    # We need at least 15-20 days of data prior to target_date to calculate 10-day averages
    start_date = (target_date - timedelta(days=40)).strftime('%Y-%m-%d')
    end_date = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')

    # 2. Get Tickers (Subset for demo; remove limit for full run)
    all_tickers = get_nasdaq_nyse_tickers()
    if ticker_limit:
        all_tickers = all_tickers[:ticker_limit]

    print(f"Downloading data for {len(all_tickers)} tickers...")
    
    # 3. Fetch Data in Batches
    batch_size = 100
    all_data = []
    
    total_batches = (len(all_tickers) + batch_size - 1) // batch_size
    for i in range(0, len(all_tickers), batch_size):
        batch = all_tickers[i : i + batch_size]
        print(f"Downloading batch {i // batch_size + 1}/{total_batches} ({batch[0]}...{batch[-1]})...")
        
        try:
            batch_data = yf.download(batch, start=start_date, end=end_date, group_by='column', progress=False, threads=True)
            if not batch_data.empty:
                # Ensure no duplicate indices (dates) which can cause concat to fail
                batch_data = batch_data[~batch_data.index.duplicated(keep='last')]
                all_data.append(batch_data)
        except Exception as e:
            print(f"Error downloading batch: {e}")
        
        # Moderate sleep to prevent rate limiting
        time.sleep(3)

    if not all_data:
        print("\n[!] Error: No data could be downloaded for any tickers. Check connectivity or Yahoo Finance status.")
        return None, None, None

    # Combine all batches
    data = pd.concat(all_data, axis=1)
    
    if data.empty:
        print("\n[!] Error: Combined data is empty.")
        return None, None, None

    # Try to find Price in common labels
    metrics = data.columns.levels[0].tolist()
    
    if 'Adj Close' in metrics and data['Adj Close'].notna().sum().sum() > 0:
        close = data['Adj Close']
    elif 'Close' in metrics:
        close = data['Close']
    else:
        # Fallback to any metric that looks like a price
        price_metrics = [m for m in metrics if 'Close' in m or 'Price' in m]
        if price_metrics:
            close = data[price_metrics[0]]
        else:
            print(f"\n[!] Error: Critical price metrics missing. Available: {metrics}")
            return None, None, None
        
    volume = data['Volume']

    # 4. Calculations
    # Turnover = Close * Volume
    turnover = close * volume
    
    # Exclude Price < $1
    turnover = turnover.where(close >= 1.0)

    # Daily Ranking (Rank 1 = Highest Turnover)
    daily_ranks = turnover.rank(axis=1, ascending=False)

    # 10-Day Metrics
    n = 10
    avg_turnover = turnover.rolling(window=n).mean()
    avg_ranking = daily_ranks.rolling(window=n).mean()
    
    # Relative Volume (Today Vol / Avg Vol of previous 10 days)
    avg_vol_10d = volume.rolling(window=n).mean().shift(1)
    rel_vol = volume / avg_vol_10d

    # 5. Filter for Target Date
    # Find the specific row in the dataframe
    try:
        idx = daily_ranks.index.get_indexer([target_date], method='pad')[0]
        actual_date = daily_ranks.index[idx]
        print(f"Targeting date: {actual_date}")
    except Exception:
        print(f"\n[!] Error: Target date {target_date.date()} out of range for the downloaded data.")
        return None, None, None

    # Consolidate results for the specific day
    results_pre = pd.DataFrame({
        'Price': close.iloc[idx],
        'Turnover': turnover.iloc[idx],
        'Ranking': daily_ranks.iloc[idx],
        'Avg_Ranking_10d': avg_ranking.iloc[idx],
        'Rel_Volume': rel_vol.iloc[idx]
    })
    
    results = results_pre.dropna()

    # --- OUTPUTS ---
    
    # Output A: Today's Top 100 by Turnover
    top_100 = results.nsmallest(100, 'Ranking')

    # Output B: Stocks meeting all conditions
    # Conditions: 
    # 1. Rank <= 100 AND Avg Rank >= 120 AND Rel Vol > 2 AND Price >= 1
    # OR 
    # 2. Rank <= 100 AND (Rank - Avg Rank <= 10) AND Rel Vol > 2 AND Price >= 1
    meets_conditions = results[
        (results['Ranking'] <= 100) & 
        (results['Rel_Volume'] > 2) &
        (results['Price'] >= 1) &
        ((results['Avg_Ranking_10d'] >= 160) | (results['Ranking'] - results['Avg_Ranking_10d'] >= 20))
    ]

    return actual_date, top_100, meets_conditions

def format_output(df_in):
    """Formats a dataframe for pretty printing without modifying the original data."""
    if df_in.empty: return df_in
    df = df_in.copy()
    df['Price'] = df['Price'].map("{:.2f}".format)
    df['Turnover'] = (df['Turnover'] / 1_000_000).map("{:.2f}".format)
    df['Ranking'] = df['Ranking'].astype(int)
    df['Avg_Ranking_10d'] = df['Avg_Ranking_10d'].astype(int)
    df['Rel_Volume'] = df['Rel_Volume'].map("{:.2f}".format)
    df.rename(columns={'Turnover': 'Turnover(M)'}, inplace=True)
    return df

# --- RUN THE ANALYSIS ---
if __name__ == "__main__":
    # Specify the date you want to analyze (None = Today)
    target_date_str = None 

    #target_date_str = '2026-5-6'

    # 1. CHECK CACHE FIRST: If results exist in DB, use them
    top_100, signals = get_from_supabase(target_date_str)
    
    if top_100 is not None:
        date_found = pd.to_datetime(target_date_str) if target_date_str else datetime.now(pytz.timezone('US/Eastern'))
    else:
        # 2. RUN FULL ANALYSIS: Only if data is missing from DB
        date_found, top_100, signals = analyze_stocks(target_date_str, ticker_limit=None)
        
        if date_found is None:
            print("\n[!] Analysis failed. Skipping save and report.")
            exit(1)
            
        # 3. SAVE RESULTS: Store for future use
        save_to_supabase(date_found.date(), top_100, signals)

    # 4. Format and Display
    print(f"\nAnalysis Results for: {date_found.date()}")
    print("\n[A] TOP 100 STOCKS BY TURNOVER (Sample):")
    print(format_output(top_100).head(10))

    print("\n[B] STOCKS MEETING ALL CONDITIONS (Surge + High Rel Vol):")
    if signals.empty:
        print("No stocks met the criteria on this day.")
    else:
        print(format_output(signals))

    # 5. SEND EMAIL REPORT
    print("\n[C] Sending Email Report...")
    # Format tables for HTML email
    top_100_html = format_output(top_100).head(20).rename_axis('Ticker').reset_index().to_html(classes='table table-striped', index=False)
    signals_html = format_output(signals).rename_axis('Ticker').reset_index().to_html(classes='table table-success', index=False) if not signals.empty else ""
    
    send_email_report(date_found.date(), top_100_html, signals_html)
