# filepath: src/step2_build_daily_mart.py
import argparse

from sqlalchemy import create_engine, text


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--db-url", required=True)
    return p.parse_args()


def main():
    args = parse_args()
    engine = create_engine(args.db_url, future=True)

    sql = """
    USE product_reviews;

    DROP TABLE IF EXISTS dm_product_review_daily;

    CREATE TABLE dm_product_review_daily AS
    SELECT
        DATE(review_date)               AS review_date,
        product_id,
        product_name,
        channel,
        COUNT(*)                        AS review_count,
        AVG(rating)                     AS avg_rating,
        SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS positive_ratio,
        SUM(CASE WHEN rating <= 2 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS negative_ratio
    FROM reviews_raw
    GROUP BY DATE(review_date), product_id, product_name, channel;

    ALTER TABLE dm_product_review_daily
      ADD COLUMN id BIGINT AUTO_INCREMENT PRIMARY KEY FIRST,
      ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      ADD UNIQUE KEY ux_dm_daily (review_date, product_id, channel);
    """
    # MySQL에서는 여러 스테이트먼트를 별도로 실행하는 게 안전함
    stmts = [s.strip() for s in sql.split(";") if s.strip()]

    with engine.begin() as conn:
        for s in stmts:
            conn.execute(text(s))

    print("[STEP2] dm_product_review_daily rebuilt.")


if __name__ == "__main__":
    main()
