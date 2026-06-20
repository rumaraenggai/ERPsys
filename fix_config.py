from modules.db import get_conn

conn = get_conn()
conn.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
conn.execute("INSERT OR REPLACE INTO config(key, value) VALUES('essl_device', '192.168.1.101:4320')")
conn.commit()

rows = conn.execute("SELECT * FROM config").fetchall()
for r in rows:
    print(dict(r))
conn.close()
print("Done.")
