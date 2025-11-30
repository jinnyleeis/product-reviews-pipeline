# filepath: src/step0_ingest_excels.py
import argparse
from pathlib import Path
import re
import logging

import pandas as pd

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[STEP0] %(levelname)s: %(message)s")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", required=True)
    p.add_argument("--staging-dir", required=True)
    return p.parse_args()


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Excel 컬럼을 내부 표준 스키마로 매핑.
    실제 파일 컬럼명에 맞게 mapping dict만 조정하면 됨.
    """
    rename_map = {
        "Review ID": "review_id",
        "Review Date": "review_date",
        "Product ID": "product_id",
        "Product Name": "product_name",
        "User ID": "user_id",
        "Channel": "channel",
        "Rating": "rating",
        "Review Text": "review_text",
    }

    logger.info("원본 컬럼: %s", list(df.columns))

    # 대소문자/공백 무시해서 유연 매핑
    cols_lower = {c.lower().strip(): c for c in df.columns}
    for logical, target in rename_map.items():
        key = logical.lower().strip()
        if key in cols_lower:
            src_col = cols_lower[key]
            logger.info("컬럼 매핑: %s -> %s", src_col, target)
            df = df.rename(columns={src_col: target})

    required = ["review_id", "review_date", "product_id", "product_name", "review_text"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # 타입 정리
    df["review_date"] = pd.to_datetime(df["review_date"], errors="coerce")
    if "rating" in df.columns:
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")

    for col in ["user_id", "channel"]:
        if col not in df.columns:
            df[col] = None

    df = df[
        [
            "review_id",
            "review_date",
            "product_id",
            "product_name",
            "user_id",
            "channel",
            "rating",
            "review_text",
        ]
    ]
    return df


def extract_period_from_filename(name: str):
    """
    reviews-YYYY-MM-DD-to-YYYY-MM-DD-[ProductReviews](_N).xlsx 패턴 파싱
    """
    m = re.match(
        r"reviews-(\d{4}-\d{2}-\d{2})-to-(\d{4}-\d{2}-\d{2})-\[ProductReviews\]",
        name,
    )
    if not m:
        return None, None
    return m.group(1), m.group(2)


def main():
    args = parse_args()
    input_dir = Path(args.input_dir)
    staging_dir = Path(args.staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    logger.info("input_dir  = %s", input_dir)
    logger.info("staging_dir= %s", staging_dir)

    excel_files = sorted(input_dir.glob("reviews-*.xlsx"))
    if not excel_files:
        raise SystemExit(f"No Excel files found in {input_dir}")

    frames = []

    for f in excel_files:
        logger.info("엑셀 읽는 중: %s", f.name)
        df = pd.read_excel(f)
        logger.info("  원본 row 수: %d", len(df))
        df = normalize_columns(df)
        logger.info("  정규화 후 row 수: %d", len(df))

        start, end = extract_period_from_filename(f.stem)
        suffix = f"_{start}_to_{end}" if start and end else ""
        out_csv = staging_dir / f"{f.stem}_cleaned.csv"
        df.to_csv(out_csv, index=False)
        logger.info("  cleaned CSV 저장: %s", out_csv)

        frames.append(df)

    all_df = pd.concat(frames, ignore_index=True)
    all_csv = staging_dir / "reviews_cleaned.csv"
    all_parquet = staging_dir / "reviews_cleaned.parquet"

    all_df.to_csv(all_csv, index=False)
    all_df.to_parquet(all_parquet, index=False)

    logger.info("모든 Excel 병합 후 row 수: %d", len(all_df))
    logger.info("merged CSV    : %s", all_csv)
    logger.info("merged Parquet: %s", all_parquet)
    logger.info("STEP0 완료")


if __name__ == "__main__":
    main()
