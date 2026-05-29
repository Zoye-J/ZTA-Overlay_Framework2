# save as update_doc_departments.py
import sqlite3

DB_PATH = 'database/api.db'

# Document assignments (id, department)
# Based on the documents created in setup_fresh_db.py
doc_assignments = [
    (1, 'General'),      # Public Service Announcement
    (2, 'General'),      # Confidential Strategy Report 
    (3, 'Defense'),      # Defense Capability Assessment
    (4, 'Intelligence'), # Intelligence Brief - TOP SECRET
    (5, 'Foreign'),      # Foreign Relations Summary
    (6, 'Defense'),      # Military Exercise Plan
    (7, 'General'),      # Digital Bangladesh Progress
]

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

for doc_id, department in doc_assignments:
    c.execute('UPDATE documents SET department = ? WHERE id = ?', (department, doc_id))
    print(f"Updated document {doc_id} to department: {department}")

# Verify
c.execute('SELECT id, title, department FROM documents')
print("\nCurrent documents:")
for row in c.fetchall():
    print(f"  Doc {row[0]}: {row[1]} -> Department: {row[2]}")

conn.commit()
conn.close()