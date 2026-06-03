# save as fix_gateway_db.py
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database', 'gateway.db')

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Check if last_activity column exists in user_sessions
c.execute("PRAGMA table_info(user_sessions)")
columns = [col[1] for col in c.fetchall()]

if 'last_activity' not in columns:
    print("Adding last_activity column to user_sessions...")
    c.execute('ALTER TABLE user_sessions ADD COLUMN last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    print("✓ Column added")

# Also add blacklisted_at if missing in token_blacklist
c.execute("PRAGMA table_info(token_blacklist)")
columns = [col[1] for col in c.fetchall()]

if 'blacklisted_at' not in columns:
    print("Adding blacklisted_at column to token_blacklist...")
    c.execute('ALTER TABLE token_blacklist ADD COLUMN blacklisted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    print("✓ Column added")

conn.commit()
conn.close()
print("\n✅ Database fixed!")