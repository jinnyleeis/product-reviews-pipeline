#!/usr/bin/env bash
# Excel → 정규화 CSV/Parquet (Step0)

{% raw %}
set -euo pipefail

echo "[STEP0] ===== START step0_ingest_excels ====="
echo "[STEP0] date: $(date)"
echo "[STEP0] pwd(before cd) : $(pwd)"
echo "[STEP0] REVIEWS_PIPELINE_BASE_DIR=${REVIEWS_PIPELINE_BASE_DIR:-<not_set>}"

BASE_DIR="${REVIEWS_PIPELINE_BASE_DIR:-$(pwd)}"
INPUT_DIR="${BASE_DIR}/data/input"
STAGING_DIR="${BASE_DIR}/data/staging"

echo "[STEP0] BASE_DIR   = ${BASE_DIR}"
echo "[STEP0] INPUT_DIR  = ${INPUT_DIR}"
echo "[STEP0] STAGING_DIR= ${STAGING_DIR}"

# ✅ 프로젝트 루트로 이동 + PYTHONPATH 보정
cd "${BASE_DIR}"
echo "[STEP0] pwd(after cd)  : $(pwd)"
export PYTHONPATH="${BASE_DIR}:${PYTHONPATH:-}"

mkdir -p "${INPUT_DIR}" "${STAGING_DIR}"

echo "[STEP0] ---- ls INPUT_DIR ----"
ls -al "${INPUT_DIR}" || echo "[STEP0] ls input_dir failed"

shopt -s nullglob
excel_files=( "${INPUT_DIR}"/reviews-*.xlsx )
shopt -u nullglob

if [ ${#excel_files[@]} -eq 0 ]; then
  echo "[STEP0] ERROR: No Excel files matching reviews-*.xlsx in ${INPUT_DIR}"
  echo "[STEP0]        예: reviews-2025-11-01-to-2025-11-07-[ProductReviews].xlsx"
  exit 1
fi

echo "[STEP0] Found ${#excel_files[@]} Excel file(s):"
for f in "${excel_files[@]}"; do
  echo "  - $(basename "$f")"
done

echo "[STEP0] which python: $(which python || echo 'python not found')"
python -V || echo "[STEP0] python -V failed (but continue)"

echo "[STEP0] Running python -m src.step0_ingest_excels ..."
python -m src.step0_ingest_excels \
  --input-dir "${INPUT_DIR}" \
  --staging-dir "${STAGING_DIR}"

status=$?
echo "[STEP0] Python exit code = ${status}"
echo "[STEP0] ===== END step0_ingest_excels ====="

exit "${status}"
{% endraw %}
