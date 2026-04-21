import os

import psycopg2


def get_connection():
    return psycopg2.connect(
        host=os.getenv("SUPABASE_DB_HOST"),
        port=os.getenv("SUPABASE_DB_PORT", "6543"),
        user=os.getenv("SUPABASE_DB_USER"),
        password=os.getenv("SUPABASE_DB_PASSWORD"),
        dbname=os.getenv("SUPABASE_DB_NAME", "postgres"),
        options="-c search_path=public",
    )
