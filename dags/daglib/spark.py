from pyspark.sql import SparkSession
from airflow.models import Connection

from .config import CLICKHOUSE_DEFAULT_HTTP_PORT


def configure_clickhouse_catalog(spark: SparkSession, catalog_name: str, clickhouse_conn: Connection):
    spark.conf.set(f'spark.sql.catalog.{catalog_name}', 'com.clickhouse.spark.ClickHouseCatalog')
    spark.conf.set(f'spark.sql.catalog.{catalog_name}.host', clickhouse_conn.host)
    spark.conf.set(f'spark.sql.catalog.{catalog_name}.protocol', 'http')
    spark.conf.set(f'spark.sql.catalog.{catalog_name}.http_port', clickhouse_conn.port or CLICKHOUSE_DEFAULT_HTTP_PORT)
    spark.conf.set(f'spark.sql.catalog.{catalog_name}.user', clickhouse_conn.login)
    spark.conf.set(f'spark.sql.catalog.{catalog_name}.password', clickhouse_conn.password)
    spark.conf.set(f'spark.sql.catalog.{catalog_name}.database', clickhouse_conn.schema)
    spark.conf.set(f'spark.{catalog_name}.write.format', 'json')
