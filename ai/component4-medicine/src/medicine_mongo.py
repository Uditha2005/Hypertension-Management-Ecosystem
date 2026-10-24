"""Shared MongoDB connection for medicine records."""
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values
from pymongo import MongoClient

CONFIG_PATH = Path(__file__).resolve().parent.parent / ".env.mongo"


@lru_cache(maxsize=1)
def get_client():
    config = dotenv_values(CONFIG_PATH)
    uri = config.get("MONGODB_URI")
    if not uri:
        raise RuntimeError("Medicine MongoDB configuration is missing.")
    client = MongoClient(
        uri,
        serverSelectionTimeoutMS=15000,
        connectTimeoutMS=10000,
        socketTimeoutMS=20000,
        appname="HyperCareMedicine",
    )
    try:
        client.admin.command("ping")
    except Exception:
        client.close()
        raise RuntimeError("Medicine MongoDB connection failed.") from None
    return client


def get_database():
    config = dotenv_values(CONFIG_PATH)
    name = config.get("MONGODB_DATABASE")
    if name != "hypercare_medicine":
        raise RuntimeError("Medicine MongoDB database name is invalid.")
    return get_client()[name]
