# filepath: dags/reviews_etl_dag.py
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "data-eng",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="product_reviews_etl",
    default_args=default_args,
    description="Excel → MySQL → Data Mart (Reviews)",
    schedule_interval=None,
    start_date=datetime(2025, 11, 1),
    catchup=False,
    tags=["reviews", "mysql", "etl"],
) as dag:

    step0 = BashOperator(
        task_id="step0_ingest_excels",
        # 템플릿 파일 이름 (DAGS_FOLDER 기준 상대 경로)
        bash_command="scripts/step0_ingest_excels.sh",
    )

    step1 = BashOperator(
        task_id="step1_load_mysql",
        bash_command="scripts/step1_load_mysql.sh",
    )

    step2 = BashOperator(
        task_id="step2_build_daily_mart",
        bash_command="scripts/step2_build_daily_mart.sh",
    )

    step3 = BashOperator(
        task_id="step3_build_summary_mart",
        bash_command="scripts/step3_build_summary_mart.sh",
    )

    step0 >> step1 >> step2 >> step3
