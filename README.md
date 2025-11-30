
# Product Reviews – Analytics & LLM Strategy

**Excel 더미 리뷰 데이터 → Airflow ETL → MySQL Data Mart → Streamlit + OpenAI LLM** 으로  
상품 리뷰를 분석하고, 자동으로 판매 전략 인사이트를 뽑아내는 파이프라인입니다.

“일관된 KPI 정의와 자동 전략 생성을 목표로,
Airflow 기반 워크플로우 + 컨테이너 환경에서 동작하는 표준 데이터 파이프라인 구조를 구현한 실습 프로젝트 입니다.

---

## 1. 문제 정의 – 왜 이 파이프라인을 만들었나

### 1-1. 비즈니스 관점(더미 데이터 도메인을 상품 리뷰로 선택한 이유) : “리뷰는 많은데, 정제된 인사이트가 없다”
상품 리뷰는 정형(KPI) + 비정형(리뷰 텍스트) 이 함께 존재해
ETL–집계–시각화–LLM 분석까지 엔드투엔드를 실습하기 좋은 도메인입니다.
실제 비즈니스에서도 리뷰는 쌓이지만 정제된 인사이트가 부족한 경우가 많아,
더미 데이터로도 현실적인 문제 상황을 자연스럽게 재현할 수 있어 선택했습니다.

### 1-2. 데이터 관점: KPI 정의와 집계 단위부터 다시 잡기

기간/상품별 리포트를 만들려면, 우선 다음이 명확해야 합니다.

- 원천 데이터 그레인: **리뷰 1건 = 1 row**
- 집계 단위:
  - `dm_product_review_daily` : `날짜 × 상품 × 채널`
  - `dm_product_review_summary` : `상품 × 채널`
- KPI 정의:
  - `review_count` – 리뷰 개수
  - `avg_rating` – 평점(1~5) 평균
  - `positive_ratio` – 평점 ≥ 4 비율
  - `negative_ratio` – 평점 ≤ 2 비율

이 프로젝트는 **“Streamlit 대시보드와 LLM 리포트가 모두 같은 Data Mart 정의를 사용”** 하도록 설계했습니다.  
따라서 화면마다 KPI가 다르게 보이는 일이 없습니다. (Source of Truth = MySQL Data Mart)

### 1-3. 기술적 동기: Streamlit 세션 기반 DAG → Airflow 워크플로우로 일반화


“기존에 파이프라인을 설계할 때 워크플로우 툴을 사용할 수 없는 환경이여서 Streamlit만으로 워크플로우의 DAG 개념을 구현한 적이 있습니다. 이를 표준 워크플로우 툴(Airflow)과 컨테이너 환경으로 옮겨와 이점을 검증해보고 싶었습니다.

기존 streamlit 기반 파이프라인 환경은:

- Airflow·dbt 같은 워크플로우 툴을 쓸 수 없고
- 실행 주기도 고정할 수 없는 **on-demand-only 환경**이라
- Streamlit 단일 페이지 안에서 **Step0~4에 해당하는 파이프라인 전체를 직접 오케스트레이션**해야 했습니다.

그래서 UI/세션 상태만으로 사실상 작은 DAG를 구현했습니다.

- **Orchestrator vs Component 분리**  
  - 한 파일(“오케스트레이션 메인 코드”)이 전체 플로우 제어만 담당하고  
  - 각 단계 UI/로직은 `components/step_X_*` 형태의 모듈에서 `display_stepX_*()` 함수로 분리  
  - Airflow로 치면 *DAG 정의 파일*과 *Task 함수들*을 분리한 구조
- **세션 상태를 DAG Edge처럼 사용**  
  - `st.session_state["current_step"]` = “현재 어느 Task까지 성공했는가” 로 사용  
  - `_can_open(step)` / `SESSION_KEYS_BY_STEP` 로  
    “어떤 선행 산출물이 있어야 이 Step을 열 수 있는지” 를 명시  
  - 사실상 **upstream 성공 여부를 조건으로 한 Task 게이팅**
- **Back 정책 + 롤백 범위 정의**  
  - `STEP_BACK_POLICY` 로 “언제 어디까지 되돌릴 수 있는지” 정의  
  - `_clear_after(step)` 에서 특정 단계 이전의 세션은 유지하고, 이후 단계 산출물만 정리  
  → Airflow에서 “특정 Task 이전까지만 유지하고, 그 이후는 재실행 대상으로 돌리는” 패턴을  
    Streamlit 세션 키로 흉내낸 구조
- **외부 시스템과의 비동기 상태 방지**  
  - 파일 업로드는 끝났지만 DB 업데이트는 안 된 상태를  
    `_unsynced_upload_state()` 로 감지하고,  
    그 상태에서는 Back 버튼을 강제로 막는 로직을 구현  
  → “중간 산출물이 외부 시스템에 반영된 후에는, 이전 Task 재실행을 제한”하는 패턴

이처럼, **Airflow에서 보통 DAG 수준에서 해결하는 문제들(의존성, 재실행, 실패 후 롤백 범위, 외부 시스템과의 정합성)을 오로지 Streamlit 세션과 버튼 정책으로 해결**해야 했고, 그 과정에서 많은 코드와 시행착오가 필요했습니다.

> 이 프로젝트는, 그때 쌓인 설계 감각을 바탕으로  
> **“표준 툴(Airflow + Docker Compose)을 써서 같은 문제를 더 표준적인 방식으로 풀어보자”**  
> 는 학습 목적의 프로젝트입니다.

---

## 2. 전체 아키텍처

```text
Excel files (data/input/*.xlsx)
        │
        ▼
[Airflow DAG: product_reviews_etl]
  step0_ingest_excels   – Excel → 정규화 CSV/Parquet
  step1_load_mysql      – CSV → MySQL reviews_raw
  step2_build_daily_mart– reviews_raw → dm_product_review_daily
  step3_build_summary_mart → dm_product_review_summary
        │
        ▼
MySQL (product_reviews DB)
        │
        ▼
Streamlit Dashboard (streamlit_app.py)
  - KPI & 시각화
  - OpenAI LLM 기반 전략 리포트
````

> 💡 기존 워크플로우를 사용하지 않은 Streamlit 세션 기반 파이프라인에서 세션 상태로 구현하던 Step0~4 의존성을
> 이제는 Airflow DAG로 명시적으로 표현하고,
> Docker Compose로 **MySQL / Airflow / Streamlit** 을 한 번에 올릴 수 있게 만든 구조입니다.

**Tech Stack**

* Orchestration: **Apache Airflow 2.9.1**
* Storage / Data Mart: **MySQL 8.0**
* Analytics App: **Streamlit**
* LLM: **OpenAI (chat.completions, `o3-mini`)**
* Infra: **Docker / docker-compose**
* Processing: **Python + Pandas + SQLAlchemy**

---

## 3. 프로젝트 구조

```text
.
├── dags
│   ├── reviews_etl_dag.py          # Airflow DAG 정의
│   └── scripts/                    # 각 Step별 Bash wrapper
├── src
│   ├── step0_ingest_excels.py      # Excel → 정규화 CSV/Parquet
│   ├── step1_load_mysql.py         # CSV → MySQL reviews_raw
│   ├── step2_build_daily_mart.py   # reviews_raw → 일별 Mart
│   └── step3_build_summary_mart.py # 일별 Mart → 요약 Mart
├── sql
│   └── schema.sql                  # MySQL 초기 스키마
├── data
│   ├── input/                      # 원본 Excel
│   └── staging/                    # 정규화된 CSV/Parquet
├── streamlit_app.py                # 분석/전략 UI
├── Dockerfile.airflow
├── Dockerfile.streamlit
└── docker-compose.yml
```

---

## 4. 데이터 모델 – Source of Truth

### 4-1. 원천 테이블: `reviews_raw`

Step0/Step1을 통해 모든 Excel 파일을 하나의 표준 스키마로 통합합니다.

```sql
CREATE TABLE reviews_raw (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    review_id     VARCHAR(64) NOT NULL,
    review_date   DATETIME NOT NULL,
    product_id    VARCHAR(64) NOT NULL,
    product_name  VARCHAR(255) NOT NULL,
    user_id       VARCHAR(64),
    channel       VARCHAR(64),
    rating        TINYINT,
    review_text   TEXT NOT NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY ux_review_unique (review_id, product_id)
);
```

특징:

* 파일마다 컬럼 구성이 조금씩 달라도, step0_normalize_columns 단계에서 공통 스키마로 깔끔하게 맞춰 줍니다.
* 또한 (review_id, product_id) 기준으로 중복 여부를 체크해 한 번만 적재하도록 설계했습니다.
→ 같은 리뷰가 여러 파일에 있어도 DB에 중복으로 들어가지 않도록(idempotent load) 처리됩니다.

### 4-2. 일별 Mart: `dm_product_review_daily`

```sql
CREATE TABLE dm_product_review_daily AS
SELECT
    DATE(review_date) AS review_date,
    product_id,
    product_name,
    channel,
    COUNT(*) AS review_count,
    AVG(rating) AS avg_rating,
    SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS positive_ratio,
    SUM(CASE WHEN rating <= 2 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS negative_ratio
FROM reviews_raw
GROUP BY DATE(review_date), product_id, product_name, channel;
```

* **하루 × 상품 × 채널** 단위의 리뷰 지표를 계산
* Streamlit의 기본 차트와 KPI가 이 테이블을 직접 참조

### 4-3. 요약 Mart: `dm_product_review_summary`

```sql
CREATE TABLE dm_product_review_summary AS
SELECT
    product_id,
    product_name,
    channel,
    SUM(review_count) AS total_reviews,
    SUM(avg_rating * review_count) / NULLIF(SUM(review_count),0) AS avg_rating,
    SUM(positive_ratio * review_count) / NULLIF(SUM(review_count),0) AS positive_ratio,
    SUM(negative_ratio * review_count) / NULLIF(SUM(review_count),0) AS negative_ratio,
    MAX(review_date) AS last_review_date
FROM dm_product_review_daily
GROUP BY product_id, product_name, channel;
```

* 기간 전체에 대한 **가중 평균**으로 정의
  (단순 평균이 아니라 리뷰 수를 weight 로 사용)
* 대시보드 상단 KPI 및 채널별 막대 그래프가 이 테이블을 사용

---

## 5. Airflow DAG – Excel → MySQL → Data Mart

### 5-1. DAG 개요

`dags/reviews_etl_dag.py`

```python
with DAG(
    dag_id="product_reviews_etl",
    description="Excel → MySQL → Data Mart (Reviews)",
    schedule_interval=None,         # 필요 시 스케줄링 가능
    start_date=datetime(2025, 11, 1),
    catchup=False,
    tags=["reviews", "mysql", "etl"],
) as dag:
    step0 = BashOperator(task_id="step0_ingest_excels", bash_command="scripts/step0_ingest_excels.sh")
    step1 = BashOperator(task_id="step1_load_mysql",   bash_command="scripts/step1_load_mysql.sh")
    step2 = BashOperator(task_id="step2_build_daily_mart",   bash_command="scripts/step2_build_daily_mart.sh")
    step3 = BashOperator(task_id="step3_build_summary_mart", bash_command="scripts/step3_build_summary_mart.sh")

    step0 >> step1 >> step2 >> step3
```

Airflow UI 기준:

* 4개 태스크가 **직렬로 연결된 단일 DAG**
* 스크린샷에서 보듯이 한 번 실행 시

  * Step0: 4개 Excel → 358건 CSV/Parquet로 정규화
  * Step1: `reviews_raw` 에 358건 insert
  * Step2/3: Daily & Summary Mart 재빌드

> 기존 streamlit 기반 파이프라인에서 세션 상태로 구현했던
> “Step0 → Step1 → Step2 → Step3 → Step4” 흐름을
> 여기서는 `step0 >> step1 >> step2 >> step3` 로 명시적으로 표현하고,
> 실패/재실행/로그를 Airflow 기본 기능에 맡기도록 설계했습니다.

<img width="982" height="361" alt="image" src="https://github.com/user-attachments/assets/05d2e4ca-22b8-43e9-a128-ce8d888a5f74" />
<p align="center"><em>Airflow에서 product_reviews_etl DAG를 등록한 화면 – Excel → MySQL → Data Mart(Reviews) 전체 파이프라인을 한 번에 실행·스케줄링.</em></p>

<img width="2048" height="883" alt="image" src="https://github.com/user-attachments/assets/3913a7ae-843e-4255-b9c5-c092ee2d7ddf" />
<p align="center"><em>Airflow product_reviews_etl DAG Graph – step0_ingest_excels → step1_load_mysql → step2_build_daily_mart → step3_build_summary_mart로 이어지는 4단계 ETL 플로우.</em></p>

<img width="2048" height="1481" alt="image" src="https://github.com/user-attachments/assets/ccf619f0-a8cc-4306-8fb5-02c3940acfe8" />
<p align="center"><em>Airflow DAG Details 뷰 – 총 실행 횟수와 성공/실패 이력, 태스크 수 등을 통해 파이프라인 안정성과 실행 성능을 모니터링.</em></p>


### 5-2. Step0 – Excel 정규화 (`step0_ingest_excels.py`)

핵심 로직:

* `data/input/reviews-*.xlsx` 패턴으로 파일 자동 스캔
* 컬럼명이 약간 달라도 `normalize_columns()` 에서 표준 스키마로 매핑
* 각 파일마다 `*_cleaned.csv` 로 저장 + 전체 병합본 `reviews_cleaned.csv/parquet` 생성

Airflow 로그 일부:

```text
[STEP0] Found 4 Excel file(s):
  - reviews-2025-11-01-to-2025-11-07-[ProductReviews].xlsx
  - reviews-2025-11-01-to-2025-11-07-[ProductReviews]_2.xlsx
  - reviews-2025-11-08-to-2025-11-14-[ProductReviews].xlsx
  - reviews-2025-11-08-to-2025-11-14-[ProductReviews]_2.xlsx
[STEP0] INFO: 모든 Excel 병합 후 row 수: 358
```

### 5-3. Step1 – MySQL 적재 (`step1_load_mysql.py`)

* 병합 CSV를 읽어 `reviews_raw` 에 insert
* 이미 존재하는 `(review_id, product_id)` 조합은 제외

```text
[STEP1] Loaded 358 rows ...
[STEP1] New rows to insert: 358
[STEP1] Insert completed.
```

### 5-4. Step2/Step3 – Data Mart 재빌드

각 Step은 MySQL에 여러 SQL statement를 순차 실행하여 테이블을 drop & create 합니다.

```text
[STEP2] dm_product_review_daily rebuilt.
[STEP3] dm_product_review_summary rebuilt.
```

Airflow 이력상

* DAG Run 1회에 4개 태스크 모두 **성공(success)**
* 이후 Streamlit에서 바로 Data Mart를 읽어서 시각화

---

## 6. Streamlit 대시보드 & LLM 전략 BI 페이지

`streamlit_app.py` 는 Data Mart를 읽어 **단일 페이지 BI + 전략 리포트**를 제공합니다.

<img width="2047" height="1417" alt="image" src="https://github.com/user-attachments/assets/2cd7e05a-3dd8-4fee-9d1d-19703a94fea8" />
<p align="center"><em>Product Reviews – Analytics & LLM Strategy 대시보드 – 일자·채널별 리뷰 수·평점과 부정 리뷰 비율을 집계하고, LLM 전략 수립용 인사이트를 한 화면에서 확인.</em></p>

<img width="589" height="433" alt="image" src="https://github.com/user-attachments/assets/646824ec-c938-4175-9ffc-9080215dee1c" />
<img width="735" height="498" alt="image" src="https://github.com/user-attachments/assets/3e8cc3da-33d2-4259-9186-80c20628c50d" />
<img width="463" height="713" alt="image" src="https://github.com/user-attachments/assets/4271b3bb-7ce4-4214-a04a-6da8588c2518" />
<img width="813" height="604" alt="image" src="https://github.com/user-attachments/assets/705d03da-02f0-42f6-9a92-053fd365989b" />
<img width="804" height="677" alt="image" src="https://github.com/user-attachments/assets/66a3f19b-0665-487b-be5d-819cad31fc03" />



### 6-1. 주요 기능

1. **사이드바 필터**

   * 상품 선택 (`product_name`)
   * 채널 선택 (`web / app / mobile / ALL`)
   * 리뷰 기간 (Date Range Picker)

2. **상단 KPI**

   * 총 리뷰 수
   * 평균 평점
   * 긍정 리뷰 비율 (rating ≥ 4)
   * 부정 리뷰 비율 (rating ≤ 2)

3. **시계열 / 채널 분석**

   * 일자별 리뷰 수 & 평균 평점 (line chart)
   * 일자별 긍/부정 리뷰 개수 (area chart)
   * 채널별 평균 평점 & 부정 리뷰 비율 (bar chart)

4. **상세 테이블**

   * `dm_product_review_daily` 필터 결과 전체
   * (옵션) `fct_product_reviews` 샘플 리뷰 텍스트

5. **LLM 기반 전략 리포트 (버튼 1번으로 생성)**

   * 감정 & 이슈 분석 (가격/품질/배송/디자인/전체만족)
   * 채널별(web/app/mobile) 전략 제안
   * 4주 실행 액션 플랜
   * 긍정 리뷰 기반 마케팅 카피 & UGC 전략

### 6-2. LLM 호출 설계

```python
client = OpenAI()

resp = client.chat.completions.create(
    model="o3-mini",
    messages=[
        {"role": "system", "content": "You are a senior growth marketer and data analyst."},
        {"role": "user", "content": prompt},
    ],
)
```

`prompt` 구성:

* 최근 14일 **Daily Metric 표** (`metrics_md`)
* 필터링된 **샘플 리뷰 텍스트** (최대 120건)
* 사용자가 직접 입력한 **비즈니스 맥락 메모**
* 각 섹션별 **세부 instruction** (감정/이슈, 채널 전략, 액션 플랜, 카피 전략)

이렇게 하면 LLM이:

* 단순 “요약”이 아니라
* **데이터 기반 전략 문서**를 섹션단위로 생성할 수 있습니다.

---

## 7. 로컬 실행 방법

### 7-1. 사전 준비

* Docker / Docker Desktop
* OpenAI API Key

```bash
export OPENAI_API_KEY="sk-..."
```

### 7-2. 컨테이너 기동

```bash
# 프로젝트 루트에서
docker-compose up -d --build
```

서비스 포트:

* MySQL: `localhost:3307` (컨테이너 내 포트는 3306)
* Airflow Web UI: `http://localhost:8080`
* Streamlit: `http://localhost:8501`

> IG 파이프라인에서는 로컬에서 Streamlit만 띄우고 세션으로 파이프라인을 유지했다면,
> 여기서는 docker-compose 한 번으로 **MySQL / Airflow / Streamlit** 환경을 같이 올리는 방식으로
> “재현 가능한 파이프라인 환경”을 만드는 연습을 했습니다.

### 7-3. 리뷰 Excel 업로드

`data/input/` 폴더에 다음 패턴으로 파일을 둡니다.

```text
reviews-YYYY-MM-DD-to-YYYY-MM-DD-[ProductReviews].xlsx
reviews-YYYY-MM-DD-to-YYYY-MM-DD-[ProductReviews]_2.xlsx
...
```

(샘플 4개는 이미 포함되어 있습니다.)

### 7-4. Airflow에서 ETL 실행

1. 브라우저에서 `http://localhost:8080` 접속
2. `product_reviews_etl` DAG **On** 으로 전환
3. 오른쪽 ▶ 버튼으로 **Trigger DAG**
4. 모든 태스크(step0~3)가 녹색(success)이 되면 ETL 완료

### 7-5. Streamlit 대시보드 확인

`http://localhost:8501` 접속 후:

1. 좌측 필터에서 **상품/채널/기간 선택**
2. 상단 KPI & 그래프 확인
3. (선택) “🧠 전략 리포트 생성” 버튼 클릭 → LLM 전략 문서 생성

---

## 8. 트러블슈팅

| 증상                                                                  | 원인                                                           | 해결 방법                                                      |
| ------------------------------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------- |
| Streamlit 상단에 “Data Mart에 데이터가 없습니다. Airflow ETL(0–3단계)을 먼저 실행하세요.” | `dm_product_review_daily`, `dm_product_review_summary` 비어 있음 | Airflow에서 `product_reviews_etl` 을 한 번 실행한 뒤 새로고침           |
| Step0에서 “No Excel files matching reviews-*.xlsx”                    | `data/input` 에 파일 없음 또는 파일명 패턴 불일치                           | 파일명을 예시 패턴에 맞게 변경하거나 폴더 위치 확인                              |
| Step1에서 MySQL 접속 오류                                                 | DB URL, 포트 문제                                                | `docker-compose.yml` 의 `REVIEWS_DB_URL` 혹은 로컬 포트(3307) 재확인 |
| LLM 섹션에 “OPENAI_API_KEY가 설정되지 않았습니다”                                | 환경 변수 미설정                                                    | Streamlit 서비스에 `OPENAI_API_KEY` env 추가 후 컨테이너 재기동          |

---

## 9.느낀 점 

* **Metric Governance & KPI 일관성 확보**

  * Data Mart 단계에서 KPI 정의를 명확히 고정해 두니(Source of Truth), 이후 Airflow·Streamlit LLM까지
모든 컴포넌트가 동일한 지표 체계를 자연스럽게 공유할 수 있었습니다.
이로인해 화면마다 KPI 계산 방식이 달라지는 문제를 원천에서 방지할 수 있었습니다.

* **Idempotent ETL의 필요성 체감**

  * Excel 파일이 여러 번 들어와도 `(review_id, product_id)` 기준으로 중복을 제거해
    운영 과정에서의 재실행 부담을 줄였습니다.
* **리뷰 텍스트와 구조화 지표의 결합 효과**

  * 리뷰 텍스트만 LLM에 전달할 때보다,
“어떤 상품을 어떤 기간·채널 기준으로 분석하고 있는지”를 구조화 지표와 함께 제공하니
모델이 단순 요약을 넘어서 구체적인 실행 전략을 제안할 수 있었습니다.
텍스트와 수치형 지표를 결합하는 방식이 전략 생성에 매우 효과적임을 확인했습니다.
* **세션 기반 워크플로우 설계를 Airflow 환경에서 재검증**

  * 기존의  Streamlit 세션만으로 DAG 구조를 에뮬레이션한 파이프라인과 달리
이번 프로젝트에서는 같은 설계를 Airflow에서 어떻게 해석하고 적용할 수 있는지 비교할 수 있었습니다.
특히 Airflow가 제공하는 태스크 의존성 선언, 실패 시 재시도, 실행 로그 및 히스토리 관리, 일관된 상태 보장 기능의 장점이 명확하게 느껴졌습니다.
“툴이 제공하는 기능은 최대한 맡기고, 비즈니스 로직에 집중해야 한다”는 것이 효율적임을 알 수 있었습니다.

* **컨테이너 기반 환경의 재현성과 관리 편의성**
MySQL, Airflow, Streamlit을 각각 Docker 이미지로 분리하고
docker-compose 한 번으로 전체 환경을 기동하는 구조를 만들면서
환경 재현·버전 관리·롤백을 실제로 경험할 수 있었습니다.
로컬 환경이 오염되거나 초기화해야 할 일이 생겨도
빠르고 일관되게 다시 올릴 수 있다는 점이 큰 장점이었습니다.

<img width="2048" height="1037" alt="image" src="https://github.com/user-attachments/assets/8f1f3e62-17d1-4d94-81c4-a681a0705365" />
<p align="center"><em>GCP Artifact Registry의 컨테이너 이미지 목록 – Streamlit, Airflow, MySQL 이미지를 분리해 저장해 재현 가능한 환경 구성 및 롤백을 지원.</em></p>

<img width="2047" height="1386" alt="image" src="https://github.com/user-attachments/assets/187c8e52-ae9a-4253-989d-e0f197b20ee7" />
<p align="center"><em>Docker Desktop에서 product-reviews-pipeline-streamlit 이미지를 분석한 화면 – 레이어별 빌드 단계와 OS 패키지 취약점 스캔 결과를 기반으로 이미지 보안성을 점검.</em></p>


---

