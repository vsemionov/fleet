import os


POSTGRES_CONN_ID = 'postgres'
CLICKHOUSE_CONN_ID = 'clickhouse'
SPARK_CONN_ID = 'spark'
OPENSKY_CONN_ID = 'opensky'

POSTGRES_DEFAULT_PORT = 5432
CLICKHOUSE_DEFAULT_PORT = 9000
CLICKHOUSE_DEFAULT_HTTP_PORT = 8123
SPARK_DEFAULT_PORT = 7077

POSTGRESQL_JDBC_JAR = os.environ['POSTGRESQL_JDBC_JAR']
CLICKHOUSE_JDBC_JAR = os.environ['CLICKHOUSE_JDBC_JAR']
CLICKHOUSE_SPARK_JAR = os.environ['CLICKHOUSE_SPARK_JAR']

AUTH_TOKENS_TABLE = 'auth_tokens'
STATES_TABLE = 'states'
CLEAN_STATES_TABLE = 'clean_states'

OPENSKY_AUTH_URL = 'https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token'
OPENSKY_STATES_URL = 'https://opensky-network.org/api/states/all'
OPENSKY_STATES_PARAMS = {'extended': 1}
OPENSKY_TIMEOUT = 30
OPENSKY_MAX_TIME_DIFF = 300
OPENSKY_MIN_AUTH_TTL = 300

SPARK_NUM_PARTITIONS = 8

PLOT_OUTPUT_DIR = '/opt/fleet/data/plots'
