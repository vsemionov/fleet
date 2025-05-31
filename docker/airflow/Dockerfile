FROM apache/airflow:3.0.1

ARG JAVA_VERSION=17
ARG SPARK_VERSION=3.5
ARG SCALA_VERSION=2.12
ARG POSTGRESQL_JDBC_VERSION=42.7.6
ARG CLICKHOUSE_JDBC_VERSION=0.6.3
ARG CLICKHOUSE_SPARK_VERSION=0.8.1

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        openjdk-${JAVA_VERSION}-jre-headless \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/java-${JAVA_VERSION}-openjdk-amd64

# https://jdbc.postgresql.org/
ENV POSTGRESQL_JDBC_JAR=/opt/fleet/jars/postgresql-${POSTGRESQL_JDBC_VERSION}.jar
RUN curl -f -sS --create-dirs -o ${POSTGRESQL_JDBC_JAR} https://jdbc.postgresql.org/download/$(basename ${POSTGRESQL_JDBC_JAR})
# https://clickhouse.com/docs/integrations/apache-spark/spark-native-connector
ENV CLICKHOUSE_JDBC_JAR=/opt/fleet/jars/clickhouse-jdbc-${CLICKHOUSE_JDBC_VERSION}-all.jar
ENV CLICKHOUSE_SPARK_JAR=/opt/fleet/jars/clickhouse-spark-runtime-${SPARK_VERSION}_${SCALA_VERSION}-${CLICKHOUSE_SPARK_VERSION}.jar
RUN curl -f -sS --create-dirs -o ${CLICKHOUSE_JDBC_JAR} https://repo1.maven.org/maven2/com/clickhouse/clickhouse-jdbc/${CLICKHOUSE_JDBC_VERSION}/$(basename ${CLICKHOUSE_JDBC_JAR})
RUN curl -f -sS --create-dirs -o ${CLICKHOUSE_SPARK_JAR} https://repo1.maven.org/maven2/com/clickhouse/spark/clickhouse-spark-runtime-${SPARK_VERSION}_${SCALA_VERSION}/${CLICKHOUSE_SPARK_VERSION}/$(basename ${CLICKHOUSE_SPARK_JAR})

USER airflow

COPY requirements.txt /opt/fleet/
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /opt/fleet/requirements.txt
