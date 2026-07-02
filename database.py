import os
import uuid
from copy import deepcopy

import dns.resolver
import bcrypt
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "flightapp_db")
MONGO_TIMEOUT_MS = int(os.getenv("MONGO_TIMEOUT_MS", "3000"))
MONGO_MAX_RETRIES = int(os.getenv("MONGO_MAX_RETRIES", "1"))
REQUIRE_MONGO = os.getenv("REQUIRE_MONGO", "").lower() in {"1", "true", "yes"}


import pickle
import atexit

DB_FILE = "/tmp/local_database.pkl" if os.getenv("VERCEL") else "local_database.pkl"

class InMemoryCollection:
    """Small Mongo-like collection used only when Atlas is unreachable locally."""

    def __init__(self, db_instance, name):
        self.db_instance = db_instance
        self.name = name
        self._documents = []

    def _matches(self, document, query):
        return all(document.get(key) == value for key, value in query.items())

    def find_one(self, query):
        for document in self._documents:
            if self._matches(document, query):
                return deepcopy(document)
        return None

    def find(self, query=None):
        query = query or {}
        return [deepcopy(doc) for doc in self._documents if self._matches(doc, query)]

    def insert_one(self, document):
        stored = deepcopy(document)
        stored.setdefault("_id", str(uuid.uuid4()))
        self._documents.append(stored)
        self.db_instance._save()
        return type("InsertOneResult", (), {"inserted_id": stored["_id"]})()

    def update_one(self, query, update, upsert=False):
        for index, document in enumerate(self._documents):
            if self._matches(document, query):
                updated = deepcopy(document)
                if "$set" in update:
                    updated.update(update["$set"])
                else:
                    updated.update(update)
                self._documents[index] = updated
                self.db_instance._save()
                return type("UpdateResult", (), {"matched_count": 1, "modified_count": 1})()

        if upsert:
            new_document = deepcopy(query)
            if "$set" in update:
                new_document.update(update["$set"])
            else:
                new_document.update(update)
            self.insert_one(new_document)

        return type("UpdateResult", (), {"matched_count": 0, "modified_count": 0})()

    def delete_one(self, query):
        for index, document in enumerate(self._documents):
            if self._matches(document, query):
                del self._documents[index]
                self.db_instance._save()
                return type("DeleteResult", (), {"deleted_count": 1})()
        return type("DeleteResult", (), {"deleted_count": 0})()


class InMemoryDatabase:
    def __init__(self):
        self.users = InMemoryCollection(self, "users")
        self.pending_users = InMemoryCollection(self, "pending_users")
        self.bookings = InMemoryCollection(self, "bookings")
        self.sell_requests = InMemoryCollection(self, "sell_requests")
        self.purchase_requests = InMemoryCollection(self, "purchase_requests")
        self.transactions = InMemoryCollection(self, "transactions")
        self.fetched_tickets = InMemoryCollection(self, "fetched_tickets")
        self._load()
        self._seed_demo_user()

    def _save(self):
        data = {
            "users": self.users._documents,
            "pending_users": self.pending_users._documents,
            "bookings": self.bookings._documents,
            "sell_requests": self.sell_requests._documents,
            "purchase_requests": self.purchase_requests._documents,
            "transactions": self.transactions._documents,
            "fetched_tickets": self.fetched_tickets._documents,
        }
        with open(DB_FILE, "wb") as f:
            pickle.dump(data, f)

    def _load(self):
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "rb") as f:
                    data = pickle.load(f)
                self.users._documents = data.get("users", [])
                self.pending_users._documents = data.get("pending_users", [])
                self.bookings._documents = data.get("bookings", [])
                self.sell_requests._documents = data.get("sell_requests", [])
                self.purchase_requests._documents = data.get("purchase_requests", [])
                self.transactions._documents = data.get("transactions", [])
                self.fetched_tickets._documents = data.get("fetched_tickets", [])
            except Exception:
                pass

    def _seed_demo_user(self):
        if not self.users.find_one({"uid": "demo-user"}):
            password = os.getenv("DEMO_USER_PASSWORD", "12345678")
            password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            self.users.insert_one({
                "uid": "demo-user",
                "email": os.getenv("DEMO_USER_EMAIL", "user@gmail.com"),
                "password": password_hash,
                "name": os.getenv("DEMO_USER_NAME", "Atta Raja"),
                "role": "user",
                "is_blocked": False,
            })


def _configure_dns():
    if os.getenv("MONGO_USE_GOOGLE_DNS", "").lower() not in {"1", "true", "yes"}:
        return

    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = ["8.8.8.8", "8.8.4.4"]
    resolver.lifetime = MONGO_TIMEOUT_MS / 1000
    resolver.timeout = max(1, resolver.lifetime / 2)
    dns.resolver.default_resolver = resolver


def _connect_to_mongo():
    if not MONGO_URI:
        raise ValueError("MONGO_URI not found in .env file.")

    print(f"Connecting to MongoDB with URI: {MONGO_URI[:25]}... (password hidden)")
    _configure_dns()

    last_error = None
    for attempt in range(1, MONGO_MAX_RETRIES + 1):
        try:
            print(f"Attempting to connect to MongoDB (Attempt {attempt}/{MONGO_MAX_RETRIES})...")
            mongo_client = MongoClient(
                MONGO_URI,
                server_api=ServerApi("1"),
                serverSelectionTimeoutMS=MONGO_TIMEOUT_MS,
                connectTimeoutMS=MONGO_TIMEOUT_MS,
            )
            mongo_client.admin.command("ping")
            print("Connected to MongoDB Atlas successfully!")
            return mongo_client, mongo_client.get_database(MONGO_DB_NAME)
        except Exception as error:
            last_error = error
            print(f"MongoDB connection attempt {attempt} failed: {error}")

    raise last_error


client = None
try:
    client, db = _connect_to_mongo()
except Exception as error:
    if REQUIRE_MONGO:
        raise
    print(f"WARNING: MongoDB unavailable, using in-memory development database. Reason: {error}")
    db = InMemoryDatabase()


users_collection = db.users
pending_users_collection = db.pending_users
bookings_collection = db.bookings
sell_requests_collection = db.sell_requests
purchase_requests_collection = db.purchase_requests
transactions_collection = db.transactions
fetched_tickets_collection = db.fetched_tickets


def get_db():
    return db

