from datetime import datetime, timedelta, timezone
from typing import Union
import logging

from airflow.models import Connection
from airflow.providers.postgres.hooks.postgres import PostgresHook
import httpx
from retryhttp import retry

from . import config


logger = logging.getLogger('airflow.task')


def refresh_opensky_auth_token(
        postgres_hook: PostgresHook,
        opensky_conn: Connection,
        min_ttl: Union[timedelta, float]
) -> tuple[str, str]:
    @retry
    def _fetch_opensky_auth_token(client_id, client_secret):
        data = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
        }
        request_time = datetime.now(timezone.utc)
        r = httpx.post(config.OPENSKY_AUTH_URL, data=data, timeout=config.OPENSKY_TIMEOUT)
        logger.info(f'Authentication response took {r.elapsed.total_seconds():.3f} s')
        r.raise_for_status()
        data = r.json()
        created_at = request_time
        expires_in = timedelta(seconds=data['expires_in'])
        token_type = data['token_type']
        access_token = data['access_token']
        return created_at, expires_in, token_type, access_token

    if not isinstance(min_ttl, timedelta):
        min_ttl = timedelta(seconds=min_ttl)

    conn_id = opensky_conn.conn_id
    client_id = opensky_conn.login
    client_secret = opensky_conn.password

    with postgres_hook.get_conn() as conn:
        with conn.cursor() as cur:
            if min_ttl.total_seconds() > 0:
                cur.execute(
                    f'select created_at, expires_in, token_type, access_token '
                    f'from {config.AUTH_TOKENS_TABLE} '
                    f'where conn_id = %s and client_id = %s '
                    f'for update',
                    (conn_id, client_id)
                )
                row = cur.fetchone()

                if row is not None:
                    created_at, expires_in, token_type, access_token = row
                    expires_at = created_at.replace(tzinfo=timezone.utc) + expires_in
                    min_expires_at = datetime.now(timezone.utc) + min_ttl
                    if expires_at > min_expires_at:
                        logger.info(f'Auth token is up to date; reusing')
                        return token_type, access_token
                    else:
                        logger.info(f'Auth token will expire soon or has expired; refreshing')

                else:
                    logger.info(f'Auth token does not exist; authenticating')

            else:
                logger.info(f'Auth token refresh forced')

            created_at, expires_in, token_type, access_token = _fetch_opensky_auth_token(client_id, client_secret)

            cur.execute(
                f'insert into {config.AUTH_TOKENS_TABLE} '
                f'(conn_id, client_id, created_at, expires_in, token_type, access_token) '
                f'values (%s, %s, %s, %s, %s, %s) '
                f'on conflict (conn_id, client_id) do update set '
                f'created_at = excluded.created_at, expires_in = excluded.expires_in, '
                f'token_type = excluded.token_type, access_token = excluded.access_token',
                (conn_id, client_id, created_at, expires_in, token_type, access_token)
            )

            logger.info(f'Authentication complete')

            return token_type, access_token
