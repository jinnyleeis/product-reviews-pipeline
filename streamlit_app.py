import os
from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

# LLM 호출용 (OpenAI)
from openai import OpenAI

# ───────────────────────────────────
# 환경 변수
# ───────────────────────────────────
DB_URL = os.environ.get(
    "REVIEWS_DB_URL",
    "mysql+mysqlconnector://root:password@localhost:3306/product_reviews",
)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


# ───────────────────────────────────
# DB 헬퍼
# ───────────────────────────────────
def _get_engine():
    return create_engine(DB_URL, future=True)


@st.cache_data(show_spinner=False)
def load_daily():
    engine = _get_engine()
    df = pd.read_sql("SELECT * FROM dm_product_review_daily", con=engine)
    return df


@st.cache_data(show_spinner=False)
def load_summary():
    engine = _get_engine()
    df = pd.read_sql("SELECT * FROM dm_product_review_summary", con=engine)
    return df


@st.cache_data(show_spinner=False)
def load_raw_reviews():
    """
    원시 리뷰 테이블 (예: fct_product_reviews)에서 샘플을 읽습니다.
    테이블이 없으면 빈 DataFrame 반환.
    """
    engine = _get_engine()
    try:
        df = pd.read_sql(
            """
            SELECT
              review_id,
              review_date,
              product_id,
              product_name,
              user_id,
              channel,
              rating,
              review_text
            FROM fct_product_reviews
            """,
            con=engine,
        )
        return df
    except Exception:
        # 테이블이 없어도 전체 앱은 동작해야 
        return pd.DataFrame()


def get_client():
    if not OPENAI_API_KEY:
        return None
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    return OpenAI()


# ───────────────────────────────────
# UI 기본 설정
# ───────────────────────────────────
st.set_page_config(page_title="Product Reviews – Strategy Studio", layout="wide")
st.title("📝 Product Reviews – Analytics & LLM Strategy")

st.markdown(
    """
MySQL Data Mart(dm_product_review_daily / dm_product_review_summary)를 기반으로  
상품별 리뷰 성과를 시각화하고, OpenAI LLM을 활용해 [리뷰 기반 판매 전략]을 제안합니다.
"""
)

# ───────────────────────────────────
# 데이터 로딩
# ───────────────────────────────────
try:
    daily = load_daily()
    summary = load_summary()
    raw_reviews = load_raw_reviews()
except Exception as e:
    st.error(f"MySQL에서 데이터를 불러오는 데 실패했습니다: {e}")
    st.stop()

if daily.empty or summary.empty:
    st.warning("Data Mart에 데이터가 없습니다. Airflow ETL(0–3단계)을 먼저 실행하세요.")
    st.stop()

# review_date 타입 정규화 (Timestamp)
daily["review_date"] = pd.to_datetime(daily["review_date"])
if not raw_reviews.empty:
    raw_reviews["review_date"] = pd.to_datetime(raw_reviews["review_date"])

# ───────────────────────────────────
# 사이드바 필터
# ───────────────────────────────────
with st.sidebar:
    st.header("필터")
    products = summary["product_name"].unique().tolist()
    sel_product = st.selectbox("상품 선택", products)

    channels = (
        ["ALL"]
        + summary.query("product_name == @sel_product")["channel"]
        .dropna()
        .unique()
        .tolist()
    )
    sel_channel = st.selectbox("채널", channels)

    # UI에는 date 타입, 내부 필터에는 Timestamp 사용
    min_date = daily["review_date"].min().date()
    max_date = daily["review_date"].max().date()

    start_d, end_d = st.date_input(
        "리뷰 기간",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if isinstance(start_d, (list, tuple)):
        # 사용자가 한 날짜만 선택했다가 다시 두 날짜로 바꾸는 등 edge case 고려
        start_d, end_d = start_d[0], start_d[1]

    # date → Timestamp
    start_ts = pd.Timestamp(start_d)
    end_ts = pd.Timestamp(end_d)

# ───────────────────────────────────
# 필터 적용
# ───────────────────────────────────
mask = daily["product_name"] == sel_product
if sel_channel != "ALL":
    mask &= daily["channel"] == sel_channel

mask &= (daily["review_date"] >= start_ts) & (daily["review_date"] <= end_ts)

daily_f = daily[mask].copy()
if daily_f.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

summary_f = summary[
    (summary["product_name"] == sel_product)
    & ((summary["channel"] == sel_channel) if sel_channel != "ALL" else True)
].copy()

# raw 리뷰 필터 (있을 때만)
raw_sample_txt = "(raw review sample not available)"
if not raw_reviews.empty:
    raw_mask = raw_reviews["product_name"] == sel_product
    if sel_channel != "ALL":
        raw_mask &= raw_reviews["channel"] == sel_channel
    raw_mask &= (raw_reviews["review_date"] >= start_ts) & (
        raw_reviews["review_date"] <= end_ts
    )
    raw_f = raw_reviews[raw_mask].copy()
    if not raw_f.empty:
        raw_f = (
            raw_f.sort_values("review_date", ascending=False)
            .head(120)[["review_date", "channel", "rating", "review_text"]]
        )
        raw_sample_txt = raw_f.to_markdown(index=False)

# ───────────────────────────────────
# 상단 KPI
# ───────────────────────────────────
daily_f["review_count"] = daily_f["review_count"].fillna(0)
daily_f["avg_rating"] = daily_f["avg_rating"].fillna(0)
daily_f["positive_ratio"] = daily_f["positive_ratio"].fillna(0)
daily_f["negative_ratio"] = daily_f["negative_ratio"].fillna(0)

c1, c2, c3, c4 = st.columns(4)
total_reviews = int(daily_f["review_count"].sum())
avg_rating = float(
    (daily_f["avg_rating"] * daily_f["review_count"]).sum()
    / max(total_reviews, 1)
)
pos_ratio = float(
    (daily_f["positive_ratio"] * daily_f["review_count"]).sum()
    / max(total_reviews, 1)
)
neg_ratio = float(
    (daily_f["negative_ratio"] * daily_f["review_count"]).sum()
    / max(total_reviews, 1)
)

c1.metric("총 리뷰 수", f"{total_reviews:,}")
c2.metric("평균 평점", f"{avg_rating:.2f}")
c3.metric("긍정 리뷰 비율", f"{pos_ratio*100:.1f}%")
c4.metric("부정 리뷰 비율", f"{neg_ratio*100:.1f}%")

st.divider()

# ───────────────────────────────────
# 그래프 고도화
# ───────────────────────────────────
# 일자별 긍/부정 리뷰 개수 계산
trend_df = daily_f.copy()
trend_df["pos_reviews"] = (
    trend_df["review_count"] * trend_df["positive_ratio"]
).fillna(0)
trend_df["neg_reviews"] = (
    trend_df["review_count"] * trend_df["negative_ratio"]
).fillna(0)

col_l, col_r = st.columns(2)

with col_l:
    st.subheader("📈 일자별 리뷰 수 & 평균 평점")
    chart_df = trend_df.sort_values("review_date")[
        ["review_date", "review_count", "avg_rating"]
    ]
    chart_df = chart_df.set_index("review_date")
    st.line_chart(chart_df[["review_count", "avg_rating"]])

with col_r:
    st.subheader("📊 일자별 긍/부정 리뷰 개수")
    ratio_df = trend_df.sort_values("review_date")[
        ["review_date", "pos_reviews", "neg_reviews"]
    ].set_index("review_date")
    st.area_chart(ratio_df)

# 채널별 집계 (선택된 기간 안에서)
channel_agg = (
    daily_f.groupby("channel")
    .apply(
        lambda g: pd.Series(
            {
                "review_count": g["review_count"].sum(),
                "avg_rating": (
                    g["avg_rating"] * g["review_count"]
                ).sum()
                / max(g["review_count"].sum(), 1),
                "neg_ratio": (
                    g["negative_ratio"] * g["review_count"]
                ).sum()
                / max(g["review_count"].sum(), 1),
            }
        )
    )
    .reset_index()
)

st.subheader("🏷 채널별 평균 평점 & 부정 리뷰 비율 (현재 필터 기간)")
if not channel_agg.empty:
    channel_chart = channel_agg.set_index("channel")[
        ["avg_rating", "neg_ratio"]
    ]
    # neg_ratio를 %로 표현
    channel_chart["neg_ratio_%"] = channel_chart["neg_ratio"] * 100
    st.bar_chart(channel_chart[["avg_rating", "neg_ratio_%"]])
else:
    st.info("해당 기간에 채널별 데이터가 없습니다.")

st.divider()

# 상세 테이블
with st.expander("일자·상품별 상세 Data Mart 보기 (dm_product_review_daily)"):
    st.dataframe(daily_f.sort_values("review_date"), use_container_width=True)

if not raw_reviews.empty and not raw_f.empty:
    with st.expander("샘플 리뷰 텍스트 보기 (fct_product_reviews)"):
        st.dataframe(raw_f, use_container_width=True)

# LLM 기반 다각도 리뷰 인사이트 & 전략
st.subheader("🤖 LLM 기반 리뷰 인사이트 & 판매 전략 제안")

client = get_client()
if client is None:
    st.warning(
        "OPENAI_API_KEY 환경 변수가 설정되지 않았습니다. "
        "LLM 호출 없이 UI만 사용됩니다."
    )

# 최근 N일 요약 텍스트 생성 (지표)
recent_df = daily_f.sort_values("review_date", ascending=False).head(14)
metrics_md = recent_df[
    [
        "review_date",
        "channel",
        "review_count",
        "avg_rating",
        "positive_ratio",
        "negative_ratio",
    ]
].to_markdown(index=False)

user_notes = st.text_area(
    "추가로 고려할 비즈니스 맥락 (옵션)",
    placeholder="예: 이번 달에는 광고 예산이 적고, 리텐션 향상이 중요합니다.",
)

def call_llm_with_context(title: str, instruction: str) -> str:
    """
    공통 컨텍스트(지표 + 샘플 리뷰 + 비즈니스 메모)에
    세부 instruction을 붙여서 LLM을 호출.
    """
    if client is None:
        return "OPENAI_API_KEY가 설정되지 않아 LLM을 호출할 수 없습니다."

    base_context = f"""
You are a data-driven marketing strategist for an e-commerce brand.

We have review-level data (rating 1–5 and Korean review_text) and daily aggregated metrics
for the product "{sel_product}" 
(channel: {sel_channel if sel_channel != "ALL" else "ALL channels"}) 
between {start_d} and {end_d}.

[Daily aggregated metrics (최근 14일 샘플)]
{metrics_md}

[Sample of raw reviews (if available)]
{raw_sample_txt}

User additional business context:
{user_notes or "(none)"}
"""

    prompt = base_context + "\n\n" + instruction

    try:
        resp = client.chat.completions.create(
            model="o3-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a senior growth marketer and data analyst.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"LLM 호출 중 오류 발생: {e}"


if st.button("🧠 전략 리포트 생성", disabled=(client is None)):
    with st.spinner("LLM이 다각도의 전략 리포트를 작성하는 중입니다..."):

        # 1) 감정 & 이슈 분석 (가격/품질/배송/디자인/전체만족)
        instruction_1 = """
우리 데이터는 결제액이 아닌 리뷰 데이터입니다.
review_text 안에서 아래 5가지 관점으로 고객 반응을 나눠서 해석해 주세요.

1) 가격: "가격 대비", "가성비", "비싸다"와 관련된 표현
2) 품질/내구성: "품질이 좋지 않습니다", "기대 이하", "재구매 의사" 등 제품 자체에 대한 평가
3) 배송/물류/CS: "배송이 너무 늦었어요", "환불하고 싶네요" 같이 배송 · 교환 · 환불 관련 표현
4) 디자인·사용 편의성: "디자인도 예쁘고 사용하기 편리합니다" 등 UI/UX, 사용성 관련 표현
5) 전반 만족도: "정말 만족스러운", "무난해요", "보통 수준" 같은 총평

rating 1~2는 명확한 불만족, 4~5는 팬층(충성 고객), 3점대는 중립이라고 가정해 분석해 주세요.

결과를 다음 구조로 정리해 주세요.
1. 위 5가지 관점별로 자주 등장하는 표현과 대표 문장을 요약
2. 관점별로 긍정/부정의 주요 원인
3. 앞으로 반드시 해결해야 하는 Top 3 이슈 (간단한 이유 포함)

답변은 한국어로 작성해 주세요.
"""
        report_1 = call_llm_with_context("감정 & 이슈 분석", instruction_1)

        # 2) 채널별 전략
        instruction_2 = """
채널(channel)은 web / app / mobile 3가지입니다.

각 채널을 다음과 같이 가정해 주세요.
- web: 검색/광고 유입이 많은 채널 (상세페이지, 가격 정보, 사진 신뢰도가 중요)
- app: 기존 고객, 푸시/리텐션 중심 채널 (재구매, 충성도 관리가 중요)
- mobile: 모바일 웹/소셜 유입 채널 (간편 결제, 빠른 배송 기대치가 높음)

선택된 product_name과 channel 정보, 지표/리뷰를 바탕으로,
1) 채널별로 자주 발생하는 이슈(가격/품질/배송/디자인/편의성)를 비교
2) 같은 상품이라도 채널별로 다른 메시지·프로모션 전략 3가지씩 제안
3) 단기적으로 집중해야 할 우선 채널 1~2개와 그 이유

답변은 한국어로 작성해 주세요.
"""
        report_2 = call_llm_with_context("채널별 전략", instruction_2)

        # 3) 우선순위 액션 플랜 (4주 실행계획)
        instruction_3 = """
운영팀이 매주 리뷰 대시보드를 보면서 액션 우선순위를 정한다고 가정합니다.

이번 분석에서는,
1) 리뷰 텍스트에서 추출한 이슈(가격, 품질, 배송, 디자인, 사용 편의성)를
   - 발생 빈도
   - rating(1~5)의 심각도
   두 기준으로 정렬해서 Top 3 이슈를 정의해 주세요.
2) 각 이슈에 대해
   - “제품 자체 개선”으로 풀 이슈인지
   - “상세페이지/사진/설명”을 고쳐야 할 이슈인지
   - “배송/물류/CS 프로세스”를 손봐야 할 이슈인지
   의 성격을 구분해 주세요.
3) 그 결과를 기준으로, 다음 4주 동안 실행할 액션 플랜(주간 단위 TODO)을 제안해 주세요.
   (예: 1주차 – 상세페이지 사진·설명 개선, 2주차 – 물류 SLA 점검 등)

답변은 한국어로 작성해 주세요.
"""
        report_3 = call_llm_with_context("우선순위 액션 플랜", instruction_3)

        # 4) 긍정 리뷰 메시지/크리에이티브 전략
        instruction_4 = """
긍정 리뷰는 마케팅 카피로 재활용하려고 합니다.

예시 표현:
- "가격 대비 성능이 정말 좋네요. 추천합니다!"
- "재구매 의사 100%입니다. 강력 추천!"
- "디자인도 예쁘고 사용하기 편리합니다."
- "배송도 빠르고 제품도 기대 이상입니다."

선택된 상품과 기간에서,
1) 자주 등장하는 긍정 표현을 3~7개 뽑아 “광고 카피/상세페이지 문구”로 쓸 수 있게 다듬어 주세요.
2) 각 긍정 포인트(가격, 품질, 디자인, 배송 등)에 대해,
   어떤 추가 리뷰/UGC를 더 모으면 설득력이 높아질지 제안해 주세요.
3) SNS/배너/앱푸시 각각에 어울리는 한 줄 카피를 2개씩 제안해 주세요.

답변은 한국어로 작성해 주세요.
"""
        report_4 = call_llm_with_context("긍정 리뷰 메시지 전략", instruction_4)

    # ── 결과 출력
    st.markdown("### 1️⃣ 감정 & 이슈 분석 (가격/품질/배송/디자인/전체만족)")
    st.markdown(report_1)

    st.markdown("---")
    st.markdown("### 2️⃣ 채널별 전략 제안 (web / app / mobile)")
    st.markdown(report_2)

    st.markdown("---")
    st.markdown("### 3️⃣ 우선순위 액션 플랜 (4주 실행 계획)")
    st.markdown(report_3)

    st.markdown("---")
    st.markdown("### 4️⃣ 긍정 리뷰 메시지 & 크리에이티브 전략")
    st.markdown(report_4)
