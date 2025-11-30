# filepath: src/step3_build_summary_mart.py
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

    DROP TABLE IF EXISTS dm_product_review_summary;

    CREATE TABLE dm_product_review_summary AS
    SELECT
        product_id,
        product_name,
        channel,
        SUM(review_count)                                  AS total_reviews,
        SUM(avg_rating * review_count) / NULLIF(SUM(review_count),0) AS avg_rating,
        SUM(positive_ratio * review_count) / NULLIF(SUM(review_count),0) AS positive_ratio,
        SUM(negative_ratio * review_count) / NULLIF(SUM(review_count),0) AS negative_ratio,
        MAX(review_date)                                   AS last_review_date
    FROM dm_product_review_daily
    GROUP BY product_id, product_name, channel;

    ALTER TABLE dm_product_review_summary
      ADD COLUMN id BIGINT AUTO_INCREMENT PRIMARY KEY FIRST,
      ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      ADD UNIQUE KEY ux_dm_summary (product_id, channel);
    """
    stmts = [s.strip() for s in sql.split(";") if s.strip()]

    with engine.begin() as conn:
        for s in stmts:
            conn.execute(text(s))

    print("[STEP3] dm_product_review_summary rebuilt.")


if __name__ == "__main__":
    main()
