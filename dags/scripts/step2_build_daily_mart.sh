# filepath: scripts/step2_build_daily_mart.sh
#!/usr/bin/env bash
set -euo pipefail

echo "[STEP2] ========= STEP2 START Build dm_product_review_daily ========="
echo "[STEP2] Raw PWD: $(pwd)"
echo "[STEP2] REVIEWS_DB_URL=${REVIEWS_DB_URL:-"(not set)"}"

: "${REVIEWS_DB_URL:?REVIEWS_DB_URL env var is required}"

# BASE_DIR 는 로그용
BASE_DIR="${REVIEWS_PIPELINE_BASE_DIR:-$(pwd)}"
echo "[STEP2] BASE_DIR=${BASE_DIR}"

cd "${BASE_DIR}"
echo "[STEP2] Changed directory to $(pwd)"
echo "[STEP2] Python will run as: python -m src.step2_build_daily_mart"

python -m src.step2_build_daily_mart \
  --db-url "${REVIEWS_DB_URL}"

rc=$?
echo "[STEP2] Python exit code = ${rc}"
echo "[STEP2] ========= STEP2 END Build dm_product_review_daily ========="
exit "${rc}"
