"""Read-only export of the benchmark app's attempts (Firestore users/*/attempts).

Only reads: one collection-group query, no writes or deletes. Keeps just the fields the
LLM reveal benchmark needs (no timings, events or user agent), for the user with the
most attempts. Needs GOOGLE_APPLICATION_CREDENTIALS and FIREBASE_PROJECT_ID.

    uv run --with firebase-admin python scripts/export_human_attempts.py out.json
"""

import json
import os
import sys
from collections import Counter, defaultdict

import firebase_admin
from firebase_admin import firestore

KEEP = ("clueId", "cryptoId", "outcome", "skipReason", "length", "revealedCount",
        "completedByReveal", "seed", "revealOrder", "v")

firebase_admin.initialize_app(options={"projectId": os.environ["FIREBASE_PROJECT_ID"]})
db = firestore.client()

by_user = defaultdict(list)
for doc in db.collection_group("attempts").stream():
    uid = doc.reference.parent.parent.id
    data = doc.to_dict()
    by_user[uid].append({k: data[k] for k in KEEP if k in data})

if not by_user:
    sys.exit("No attempts found")
uid = max(by_user, key=lambda u: len(by_user[u]))
rows = sorted(by_user[uid], key=lambda a: a["clueId"])
print(f"users: {len(by_user)}; using the one with {len(rows)} attempts")
print("outcomes:", dict(Counter(a["outcome"] for a in rows)))
print("with revealOrder:", sum(1 for a in rows if a.get("revealOrder")))
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(rows, f, indent=1)
