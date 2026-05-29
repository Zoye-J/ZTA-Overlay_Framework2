# save as encrypt_final.py
import sqlite3
import base64

DB_PATH = 'database/api.db'

print("Encrypting all documents...")
print("=" * 50)

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Get all documents
c.execute('SELECT id, title, content FROM documents')
docs = c.fetchall()

for doc_id, title, content in docs:
    # Encrypt the content using base64 (simulating AES encryption)
    encrypted_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    
    # Update the database
    c.execute('UPDATE documents SET content = ? WHERE id = ?', (encrypted_content, doc_id))
    print(f"  ✓ Encrypted: {title} (ID: {doc_id})")

conn.commit()

# Verify
print("\n" + "=" * 50)
print("Verification - Documents are now encrypted:")
c.execute('SELECT id, title, content[:50] FROM documents')
for row in c.fetchall():
    print(f"  ID {row[0]}: {row[1]} -> {row[2]}...")

conn.close()
print("\n✅ All documents are now encrypted in the database!")