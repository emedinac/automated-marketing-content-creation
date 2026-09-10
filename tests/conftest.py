import os

# Tests use injected/in-memory stores and must not connect to a developer's
# local PostgreSQL instance configured in .env.
os.environ["DATABASE_URL"] = ""
