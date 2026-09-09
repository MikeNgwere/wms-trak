"""
Database connection helper, using a pooled connection shared across
the Streamlit session (instead of opening a fresh connection per
query, which was the main cause of sluggishness over the network).

IMPORTANT (lesson carried over from MMADF): on WSL2 / many cloud
sandboxes, direct IPv6 connections to Supabase fail. Use the Session
Pooler connection string (port 5432 on aws-x-<region>.pooler.supabase.com),
not the direct db.<project>.supabase.co host.
"""
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import psycopg2.pool
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")


@st.cache_resource
def get_pool():
    return psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=DATABASE_URL)


@contextmanager
def get_conn():
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def fetch_all(query: str, params: tuple = ()):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            return cur.fetchall()


def fetch_one(query: str, params: tuple = ()):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            return cur.fetchone()


def execute(query: str, params: tuple = ()):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)