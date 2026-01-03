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
init_database(DB_PATH)

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


def collect_trends_task(country_code: str) -> int:
    """Task function to collect trends for a specific country code.

    Args:
        country_code: Two-letter country code

    Returns:
        Number of trends collected
    """
    try:
        count = collect_trends_for_region(country_code, DB_PATH)
        logger.info(f"Successfully collected {count} trends for {country_code}")
        return count
    except Exception as e:
        logger.error(f"Failed to collect trends for {country_code}: {e}")
        raise


# Load geo codes and create a task for each country
try:
    geo_codes = load_geo_codes(os.path.join(os.path.dirname(__file__), '..', 'geo_codes'))
    logger.info(f"Loaded {len(geo_codes)} country codes")
except Exception as e:
    logger.error(f"Failed to load geo codes: {e}")
    geo_codes = []

# Create a task for each country code
for geo_info in geo_codes:
    code = geo_info['code']
    task = PythonOperator(
        task_id=f'collect_{code}',
        python_callable=collect_trends_task,
        op_kwargs={'country_code': code},
        dag=dag,
    )
    # Add task to DAG (dependencies are implicit - all run in parallel)

# Log DAG info
logger.info(f"Google Trends Collector DAG created with {len(dag.tasks)} tasks")
