from sqlalchemy import Engine, inspect, text


def add_legacy_coordinate_columns(engine: Engine) -> None:
    """Add nullable CRS columns without assigning a CRS to ambiguous legacy rows."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    additions: list[tuple[str, str]] = []
    if "locations" in table_names:
        columns = {column["name"] for column in inspector.get_columns("locations")}
        if "source_crs" not in columns:
            additions.append(("locations", "source_crs"))
    if "geofences" in table_names:
        columns = {column["name"] for column in inspector.get_columns("geofences")}
        if "crs" not in columns:
            additions.append(("geofences", "crs"))

    if not additions:
        return
    if engine.dialect.name != "sqlite":
        missing = ", ".join(f"{table}.{column}" for table, column in additions)
        raise RuntimeError(f"Database migration required for coordinate columns: {missing}")
    with engine.begin() as connection:
        for table_name, column_name in additions:
            connection.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} VARCHAR(20)")
            )
