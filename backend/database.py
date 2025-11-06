import os
from typing import Any, Dict, List, Optional
from datetime import datetime
from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection

DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "portfolio_pal")

_client = MongoClient(DATABASE_URL)
db = _client[DATABASE_NAME]

# Ensure common indexes
for name, keys in {
    "user": [("email", ASCENDING)],
    "activity": [("user_id", ASCENDING), ("created_at", ASCENDING)],
    "passwordreset": [("token", ASCENDING), ("expires_at", ASCENDING)],
}.items():
    try:
        col = db[name]
        for key, direction in keys:
            col.create_index([(key, direction)], background=True, unique=True if key == "email" and name == "user" else False)
    except Exception:
        # Index creation is best-effort
        pass


def now_ts() -> datetime:
    return datetime.utcnow()


def create_document(collection_name: str, data: Dict[str, Any]) -> str:
    col: Collection = db[collection_name]
    data = {**data, "created_at": data.get("created_at", now_ts()), "updated_at": data.get("updated_at", now_ts())}
    res = col.insert_one(data)
    return str(res.inserted_id)


def update_document(collection_name: str, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> int:
    col: Collection = db[collection_name]
    update_dict["updated_at"] = now_ts()
    res = col.update_one(filter_dict, {"$set": update_dict})
    return res.modified_count


def get_documents(collection_name: str, filter_dict: Optional[Dict[str, Any]] = None, limit: int = 100, sort: Optional[List] = None) -> List[Dict[str, Any]]:
    col: Collection = db[collection_name]
    cur = col.find(filter_dict or {})
    if sort:
        cur = cur.sort(sort)
    if limit:
        cur = cur.limit(int(limit))
    items: List[Dict[str, Any]] = []
    for doc in cur:
        doc["_id"] = str(doc["_id"])  # stringify
        items.append(doc)
    return items


def get_one(collection_name: str, filter_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    col: Collection = db[collection_name]
    doc = col.find_one(filter_dict)
    if doc:
        doc["_id"] = str(doc["_id"])  # stringify
    return doc


def delete_document(collection_name: str, filter_dict: Dict[str, Any]) -> int:
    col: Collection = db[collection_name]
    res = col.delete_one(filter_dict)
    return res.deleted_count
