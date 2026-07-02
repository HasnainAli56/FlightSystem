from pymongo import MongoClient
from pymongo.server_api import ServerApi
import os
from dotenv import load_dotenv

load_dotenv()
uri = os.getenv("MONGO_URI")

print(f"Testing connection with URI: {uri[:20]}... (hidden)")

client = MongoClient(uri, server_api=ServerApi('1'))

try:
    client.admin.command('ping')
    print("✅ Ping successful! Connected to MongoDB Atlas.")
    print("Databases available:", client.list_database_names())
except Exception as e:
    print(f"❌ Connection failed: {e}")
