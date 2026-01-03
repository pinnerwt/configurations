"""
Apache Airflow DAG for Google Trends hourly data collection.

Collects Google Trends data from all 243 regions every hour.
Each region is processed as a separate task running in parallel.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
import sys
import os
import logging

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from trend.scraper import collect_trends_for_region
from trend.geo_codes import load_geo_codes
from trend.database import init_database

logger = logging.getLogger(__name__)

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'trends.db')

# Initialize database on DAG load
logger.info(f"Initializing database at {DB_PATH}")
init_database(DB_PATH)
logger.info("Database initialization complete")

# Default arguments for DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# Create DAG
dag = DAG(
    'google_trends_collector',
    default_args=default_args,
    start_date=datetime(2026, 1, 3),
    description='Collect Google Trends data hourly across all 243 regions',
    schedule='0 * * * *',  # Every hour at minute 0
    catchup=False,  # Don't backfill on resume
    tags=['google-trends', 'data-collection'],
)


def collect_trends_task(country_code: str, **context) -> int:
    """Task function to collect trends for a specific country code.

    Args:
        country_code: Two-letter country code

    Returns:
        Number of trends collected
    """
    try:
        run_id = context.get('run_id')
        dag_id = context.get('dag').dag_id if context.get('dag') else None
        task_id = context.get('task').task_id if context.get('task') else None
        try_number = context.get('ti').try_number if context.get('ti') else None
        logger.info(
            "Starting trends collection for %s (dag_id=%s, task_id=%s, run_id=%s, try_number=%s, db_path=%s)",
            country_code,
            dag_id,
            task_id,
            run_id,
            try_number,
            DB_PATH,
        )
        count = collect_trends_for_region(country_code, DB_PATH)
        logger.info(
            "Successfully collected %s trends for %s (dag_id=%s, task_id=%s, run_id=%s, try_number=%s)",
            count,
            country_code,
            dag_id,
            task_id,
            run_id,
            try_number,
        )
        return count
    except Exception as e:
        logger.exception(
            "Failed to collect trends for %s (dag_id=%s, task_id=%s, run_id=%s, try_number=%s)",
            country_code,
            dag_id,
            task_id,
            run_id,
            try_number,
        )
        raise


# Load geo codes and create a task for each country
try:
    geo_codes_path = '/x/home_pgi/trend/geo_codes'
    logger.info(f"Loading geo codes from {geo_codes_path}")
    geo_codes = load_geo_codes(geo_codes_path)
    logger.info(f"Loaded {len(geo_codes)} country codes")
except Exception as e:
    logger.exception("Failed to load geo codes")
    geo_codes = []

# Create a task for each country code
for geo_info in geo_codes:
    code = geo_info['code']
    logger.debug(f"Creating task for country code {code}")
    task = PythonOperator(
        task_id=f'collect_{code}',
        python_callable=collect_trends_task,
        op_kwargs={'country_code': code},
        dag=dag,
    )
    # Add task to DAG (dependencies are implicit - all run in parallel)

# Log DAG info
logger.info(f"Google Trends Collector DAG created with {len(dag.tasks)} tasks")
