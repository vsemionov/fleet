begin;

drop table if exists auth_tokens;
create table if not exists auth_tokens (
    conn_id varchar(128),
    client_id varchar(128),
    created_at timestamp not null,
    expires_in interval not null,
    token_type varchar(128) not null,
    access_token text not null,
    primary key (conn_id, client_id)
);

commit;
