"""Create datasource tables on remote using sqlite3 directly."""
import sqlite3
import os

db_path = '/data/intelli/engine/.deer-flow/data/deerflow.db'
print(f"DB exists: {os.path.exists(db_path)}")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Create datasource table
cur.execute("""
    CREATE TABLE IF NOT EXISTS datasource (
        id VARCHAR(64) PRIMARY KEY,
        user_id VARCHAR(64) NOT NULL,
        name VARCHAR(128) NOT NULL,
        description TEXT DEFAULT '',
        type VARCHAR(32) NOT NULL,
        status VARCHAR(20) DEFAULT 'ready',
        icon VARCHAR(64) DEFAULT '',
        config_json TEXT DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        deleted INTEGER DEFAULT 0
    )
""")

# Create conversation_datasource table
cur.execute("""
    CREATE TABLE IF NOT EXISTS conversation_datasource (
        id VARCHAR(64) PRIMARY KEY,
        conversation_id VARCHAR(64) NOT NULL REFERENCES threads_meta(thread_id) ON DELETE CASCADE,
        datasource_id VARCHAR(64) NOT NULL REFERENCES datasource(id) ON DELETE CASCADE,
        alias VARCHAR(128),
        mount_path VARCHAR(256),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

# Create indexes
cur.execute("CREATE INDEX IF NOT EXISTS idx_datasource_user_id ON datasource(user_id)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_datasource_type ON datasource(type)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_cds_conversation_id ON conversation_datasource(conversation_id)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_cds_datasource_id ON conversation_datasource(datasource_id)")

conn.commit()

# Verify
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cur.fetchall()
print(f"Tables: {[t[0] for t in tables]}")

conn.close()
print("Done!")
