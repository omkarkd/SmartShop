import os


MONGO_URI = None
DB_NAME = None


def load():
    global MONGO_URI, DB_NAME
    if MONGO_URI is not None:
        return MONGO_URI, DB_NAME
    MONGO_URI = os.environ.get("MONGO_URI")
    DB_NAME = os.environ.get("DB_NAME", "smartshop")
    if not MONGO_URI:
        raise RuntimeError(
            "MONGO_URI environment variable is required. "
            "Set it to your MongoDB connection string."
        )
    return MONGO_URI, DB_NAME
