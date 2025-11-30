# filepath: scripts/step1_load_mysql.sh
#!/usr/bin/env bash
set -euo pipefail

echo "[STEP1] ========= STEP1 START Load MySQL ========="
echo "[STEP1] Raw PWD: $(pwd)"
echo "[STEP1] REVIEWS_PIPELINE_BASE_DIR=${REVIEWS_PIPELINE_BASE_DIR:-"(not set)"}"
echo "[STEP1] REVIEWS_DB_URL=${REVIEWS_DB_URL:-"(not set)"}"

BASE_DIR="${REVIEWS_PIPELINE_BASE_DIR:-$(pwd)}"
STAGING_DIR="${BASE_DIR}/data/staging"

echo "[STEP1] BASE_DIR=${BASE_DIR}"
echo "[STEP1] STAGING_DIR=${STAGING_DIR}"

: "${REVIEWS_DB_URL:?REVIEWS_DB_URL env var is required, e.g. mysql+mysqlconnector://user:pwd@host:3306/product_reviews}"

echo "[STEP1] ===== Listing STAGING_DIR ====="
ls -al "${STAGING_DIR}" || {
  echo "[STEP1][ERROR] STAGING_DIR does not exist"
  exit 1
}

cd "${BASE_DIR}"
echo "[STEP1] Changed directory to $(pwd)"
echo "[STEP1] Python will run as: python -m src.step1_load_mysql"

python -m src.step1_load_mysql \
  --staging-dir "${STAGING_DIR}" \
  --db-url "${REVIEWS_DB_URL}"

rc=$?
echo "[STEP1] Python exit code = ${rc}"
echo "[STEP1] ========= STEP1 END Load MySQL ========="
exit "${rc}"
