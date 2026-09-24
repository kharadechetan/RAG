from pymongo import MongoClient
from langgraph.checkpoint.mongodb import MongoDBSaver

class DatabaseStore:
    client: MongoClient = None
    db = None
    checkpointer: MongoDBSaver = None

db_store = DatabaseStore()
