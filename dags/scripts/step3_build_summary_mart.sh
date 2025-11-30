# filepath: scripts/step3_build_summary_mart.sh
#!/usr/bin/env bash
set -euo pipefail

echo "[STEP3] ========= STEP3 START Build dm_product_review_summary ========="
echo "[STEP3] Raw PWD: $(pwd)"
echo "[STEP3] REVIEWS_DB_URL=${REVIEWS_DB_URL:-"(not set)"}"

: "${REVIEWS_DB_URL:?REVIEWS_DB_URL env var is required}"

BASE_DIR="${REVIEWS_PIPELINE_BASE_DIR:-$(pwd)}"
echo "[STEP3] BASE_DIR=${BASE_DIR}"

cd "${BASE_DIR}"
echo "[STEP3] Changed directory to $(pwd)"
echo "[STEP3] Python will run as: python -m src.step3_build_summary_mart"

python -m src.step3_build_summary_mart \
  --db-url "${REVIEWS_DB_URL}"

rc=$?
echo "[STEP3] Python exit code = ${rc}"
echo "[STEP3] ========= STEP3 END Build dm_product_review_summary ========="
exit "${rc}"
