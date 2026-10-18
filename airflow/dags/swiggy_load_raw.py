"""Stage each CSV batch and merge by Swiggy keys; retries do not append duplicates."""
import os
import re

TABLE_KEYS = {
    "cities": ("CITY_ID",),
    "cuisines": ("CUISINE_ID",),
    "restaurants": ("LISTING_ID",),
    "restaurant_cuisines": ("LISTING_ID", "CUISINE_ID"),
}


def main():
    import snowflake.connector
    stages = list(dict.fromkeys(filter(None, [os.getenv("SWIGGY_S3_STAGE"), os.getenv("SWIGGY_ADLS_STAGE")])))
    if not stages:
        stages = [os.environ.get("SWIGGY_RAW_STAGE", "SWIGGY.RAW.SWIGGY_LOCAL_STAGE")]
    for stage in stages:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*([.][A-Za-z_][A-Za-z0-9_]*){2}", stage):
            raise ValueError("Source stage must be DATABASE.SCHEMA.STAGE")
    passphrase = os.environ.get("DBT_SNOWFLAKE_KEY_PASSPHRASE")
    if not passphrase:
        raise ValueError("Set DBT_SNOWFLAKE_KEY_PASSPHRASE privately in .env before running the DAG")
    with snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        role=os.environ["SNOWFLAKE_ROLE"],
        warehouse="SWIGGY_WH", database="SWIGGY", schema="RAW",
        private_key_file="/opt/airflow/keys/swiggy_dbt_key.p8",
        private_key_file_pwd=passphrase,
    ) as connection:
        with connection.cursor() as cursor:
            for table, keys in TABLE_KEYS.items():
                target = f"SWIGGY.RAW.{table}"
                batch = f"SWIGGY.RAW.TEMP_AIRFLOW_{table}"
                cursor.execute(f"CREATE TEMPORARY TABLE {batch} LIKE {target}")
                pattern = rf"(.*/)?{table}(_[0-9]+)?[.]csv"
                # FORCE is safe here: the destination is a fresh session-local temporary table.
                for stage in stages:
                    cursor.execute(
                        f"COPY INTO {batch} FROM @{stage} "
                        f"FILE_FORMAT = (FORMAT_NAME = 'SWIGGY.RAW.CSV_FMT') "
                        f"PATTERN = '{pattern}' ON_ERROR = 'ABORT_STATEMENT' FORCE = TRUE"
                    )
                    print(f"{table}: staged {cursor.fetchall()}")
                cursor.execute(f"SELECT COUNT(*) FROM {batch}")
                if cursor.fetchone()[0] == 0:
                    raise ValueError(f"No staged rows found for {table}; check the stage and filenames")
                columns = [column[0] for column in cursor.execute(f"SELECT * FROM {batch} LIMIT 0").description]
                quoted = [f'"{column}"' for column in columns]
                source = f"(SELECT DISTINCT * FROM {batch})"
                key_list = ', '.join(f'"{key}"' for key in keys)
                nulls = ' OR '.join(f'"{key}" IS NULL' for key in keys)
                cursor.execute(f"SELECT COUNT(*) FROM {source} WHERE {nulls}")
                if cursor.fetchone()[0]:
                    raise ValueError(f"Null keys in staged {table}")
                cursor.execute(f"SELECT COUNT(*) FROM (SELECT {key_list} FROM {source} GROUP BY {key_list} HAVING COUNT(*) > 1)")
                if cursor.fetchone()[0]:
                    raise ValueError(f"Conflicting staged records for {table}; supply one current version per key")
                cursor.execute(f"SELECT COUNT(*) FROM (SELECT {key_list} FROM {target} GROUP BY {key_list} HAVING COUNT(*) > 1)")
                if cursor.fetchone()[0]:
                    raise ValueError(f"Duplicate keys already exist in {target}; repair before merging")
                on_clause = ' AND '.join(f't."{key}" = s."{key}"' for key in keys)
                updates = ', '.join(f't.{column} = s.{column}' for column, name in zip(quoted, columns) if name not in keys)
                when_matched = f"WHEN MATCHED THEN UPDATE SET {updates} " if updates else ""
                cursor.execute(
                    f"MERGE INTO {target} t USING {source} s ON {on_clause} "
                    + when_matched
                    + f"WHEN NOT MATCHED THEN INSERT ({', '.join(quoted)}) "
                    + f"VALUES ({', '.join('s.' + column for column in quoted)})"
                )
                print(f"{table}: merged {cursor.fetchall()}")


if __name__ == "__main__":
    main()
