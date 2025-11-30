# filepath: src/step1_load_mysql.py
import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--staging-dir", required=True)
    p.add_argument("--db-url", required=True)  # mysql+mysqlconnector:// ~~
    return p.parse_args()


def ensure_db_schema(engine):
    ddl = """
    CREATE TABLE IF NOT EXISTS reviews_raw (
        id            BIGINT AUTO_INCREMENT PRIMARY KEY,
        review_id     VARCHAR(64) NOT NULL,
        review_date   DATETIME NOT NULL,
        product_id    VARCHAR(64) NOT NULL,
        product_name  VARCHAR(255) NOT NULL,
        user_id       VARCHAR(64) NULL,
        channel       VARCHAR(64) NULL,
        rating        TINYINT NULL,
        review_text   TEXT NOT NULL,
        created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY ux_review_unique (review_id, product_id)
    );
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def main():   
    args = parse_args()
    staging_dir = Path(args.staging_dir)
    db_url = args.db_url

    merged_csv = staging_dir / "reviews_cleaned.csv"
    if not merged_csv.exists():
        raise SystemExit(f"Missing {merged_csv}; run Step0 first.")

    df = pd.read_csv(merged_csv, parse_dates=["review_date"])
    print(f"[STEP1] Loaded {len(df):,} rows from {merged_csv}")

    engine = create_engine(db_url, future=True)
    ensure_db_schema(engine)

    # 중복 제거 후 적재 (이미 있는 review_id/product_id는 제외하는 로직)
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT review_id, product_id FROM reviews_raw")
        ).fetchall()
        existing_set = {(r[0], r[1]) for r in existing}

    mask_new = ~df.apply(
        lambda r: (str(r["review_id"]), str(r["product_id"])) in existing_set, axis=1
    )
    df_new = df[mask_new].copy()
    print(f"[STEP1] New rows to insert: {len(df_new):,}")

    if df_new.empty:
        print("[STEP1] Nothing new to insert.")
        return

    df_new.to_sql("reviews_raw", con=engine, if_exists="append", index=False)
    print("[STEP1] Insert completed.")


if __name__ == "__main__":
    main()
