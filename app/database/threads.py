from datetime import datetime, timezone
from app.database.mongodb import db_store

def create_thread_metadata(thread_id: str, user_id: str | None = None):
    now = datetime.now(timezone.utc)
    owner = user_id or "default_user"
    db_store.db["threads"].insert_one({
        "_id": thread_id,
        "user_id": owner,
        "created_at": now,
        "updated_at": now
    })
    return {"thread_id": thread_id, "created_at": now, "updated_at": now, "user_id": owner}

def list_threads_metadata():
    threads = db_store.db["threads"].find().sort("updated_at", -1)
    return [
        {
            "thread_id": t["_id"],
            "created_at": t["created_at"],
            "updated_at": t["updated_at"]
        } for t in threads
    ]

def get_thread_metadata(thread_id: str):
    return db_store.db["threads"].find_one({"_id": thread_id})

def update_thread_metadata(thread_id: str):
    now = datetime.now(timezone.utc)
    db_store.db["threads"].update_one(
        {"_id": thread_id},
        {"$set": {"updated_at": now}}
    )

def delete_thread_metadata(thread_id: str):
    # Delete metadata
    db_store.db["threads"].delete_one({"_id": thread_id})
    # Delete LangGraph checkpoint collections for this thread
    db_store.db["checkpoints"].delete_many({"thread_id": thread_id})
    db_store.db["checkpoint_writes"].delete_many({"thread_id": thread_id})
    db_store.db["checkpoint_blobs"].delete_many({"thread_id": thread_id})
