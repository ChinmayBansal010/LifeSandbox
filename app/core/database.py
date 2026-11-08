from sqlalchemy.engine import make_url


def normalize_database_url(database_url: str) -> tuple[str, dict[str, str]]:
    """Translate libpq SSL query parameters into asyncpg connection arguments."""
    url = make_url(database_url)
    connect_args: dict[str, str] = {}

    if url.get_backend_name() == "postgresql" and url.get_driver_name() == "asyncpg":
        query = dict(url.query)
        sslmode = query.pop("sslmode", None)
        query.pop("channel_binding", None)
        ssl = query.pop("ssl", None)

        ssl_setting = ssl if ssl is not None else sslmode
        if ssl_setting is not None:
            connect_args["ssl"] = str(ssl_setting)

        url = url.set(query=query)

    return url.render_as_string(hide_password=False), connect_args
