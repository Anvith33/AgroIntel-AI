import pandas as pd
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
ARCHIVE_DIR = BASE_DIR / "archive" / "csv"
OUTPUT_FILE = BASE_DIR / "real_historical_prices.csv"

# Target years (2019 to 2024 for 5+ years of data)
TARGET_YEARS = [2019, 2020, 2021, 2022, 2023, 2024]

# Crop mappings to standard names
CROP_MAPPINGS = {
    "wheat": "wheat",
    "rice": "rice",
    "paddy": "rice", # Often listed as Paddy
    "paddy(dhan)": "rice",
    "maize": "maize"
}

def process_data():
    logger.info("Starting historical data processing...")
    all_data = []

    for year in TARGET_YEARS:
        file_path = ARCHIVE_DIR / f"{year}.csv"
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            continue

        logger.info(f"Processing {year}.csv...")
        
        # Read only required columns to save memory
        try:
            df = pd.read_csv(
                file_path, 
                usecols=["Commodity", "Arrival_Date", "Modal_Price"],
                parse_dates=["Arrival_Date"],
                dayfirst=False, # Often dates are YYYY-MM-DD or DD/MM/YYYY, pd.to_datetime handles it better
                on_bad_lines='skip',
                low_memory=False
            )
        except Exception as e:
            logger.error(f"Error reading {year}.csv: {e}")
            continue
            
        # Standardize commodity names
        df["Commodity"] = df["Commodity"].astype(str).str.lower().str.strip()
        
        # Keep only our target crops
        df["crop"] = df["Commodity"].map(CROP_MAPPINGS)
        df = df.dropna(subset=["crop", "Modal_Price"])
        
        # Convert prices to numeric, handling errors
        df["Modal_Price"] = pd.to_numeric(df["Modal_Price"], errors="coerce")
        df = df.dropna(subset=["Modal_Price"])
        
        # Make sure Arrival_Date is datetime
        df["Arrival_Date"] = pd.to_datetime(df["Arrival_Date"], errors="coerce")
        df = df.dropna(subset=["Arrival_Date"])

        # Group by Date and Crop, calculating the national average modal price
        daily_avg = df.groupby(["Arrival_Date", "crop"])["Modal_Price"].mean().reset_index()
        all_data.append(daily_avg)

    if not all_data:
        logger.error("No data processed!")
        return

    logger.info("Combining all years...")
    final_df = pd.concat(all_data, ignore_index=True)
    
    # In case there are duplicates from grouping across different chunks/years, group again
    final_df = final_df.groupby(["Arrival_Date", "crop"])["Modal_Price"].mean().reset_index()
    final_df = final_df.sort_values("Arrival_Date")

    # Rename columns to match what train.py expects: 'ds', 'y', 'crop'
    final_df.rename(columns={"Arrival_Date": "ds", "Modal_Price": "y"}, inplace=True)
    
    # ── Forward fill missing dates ──
    # Mandis are often closed on weekends or holidays, resulting in missing dates.
    # We need continuous daily data for time series models.
    logger.info("Forward filling missing dates for continuous time series...")
    
    clean_dfs = []
    crops = final_df["crop"].unique()
    
    # Find global min and max dates
    min_date = final_df["ds"].min()
    max_date = final_df["ds"].max()
    full_date_range = pd.date_range(start=min_date, end=max_date, freq="D")
    
    for crop in crops:
        crop_df = final_df[final_df["crop"] == crop].set_index("ds")
        # Reindex to full date range, which introduces NaNs for missing days
        crop_df = crop_df.reindex(full_date_range)
        crop_df["crop"] = crop
        # Forward fill the prices
        crop_df["y"] = crop_df["y"].ffill()
        # Backward fill in case the very first day was NaN
        crop_df["y"] = crop_df["y"].bfill()
        
        crop_df = crop_df.reset_index().rename(columns={"index": "ds"})
        clean_dfs.append(crop_df)
        
    final_clean_df = pd.concat(clean_dfs, ignore_index=True)

    # Remove extreme outliers (prices > 15000 or < 500 for these staple crops)
    final_clean_df.loc[final_clean_df["y"] > 15000, "y"] = np.nan
    final_clean_df.loc[final_clean_df["y"] < 500, "y"] = np.nan
    final_clean_df["y"] = final_clean_df.groupby("crop")["y"].transform(lambda x: x.ffill().bfill())

    logger.info(f"Final dataset shape: {final_clean_df.shape}")
    logger.info(f"Date range: {min_date.date()} to {max_date.date()}")
    
    final_clean_df.to_csv(OUTPUT_FILE, index=False)
    logger.info(f"Saved real historical prices to: {OUTPUT_FILE}")

if __name__ == "__main__":
    process_data()
