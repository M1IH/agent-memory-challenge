"""Offline BEAM batch-balanced Top-100 proxy; never writes to production Search.

Only source message IDs score the reordered results. The first five lexical
results stay fixed, then results 6-300 are interleaved by original Add batch.
"""

import hashlib
import json
import pyarrow.parquet as pq

SOURCE_SHA256 = 'c0519be25907005ba873c927c50877471d550873039d96c041554d0075a78ace'
REPORT_SHA256 = '14108a009a8538596e941c9b546a906f25739c4918fd89eca4e049479c4a29eb'

assert hashlib.sha256(open('data/beam-100k.parquet', 'rb').read()).hexdigest() == SOURCE_SHA256
assert hashlib.sha256(open('data/beam-100k-dev-14-top300.json', 'rb').read()).hexdigest() == REPORT_SHA256
source = pq.read_table('data/beam-100k.parquet').to_pylist()
batch_by_conversation = {
    str(row['conversation_id']): {
        message['id']: batch
        for batch, messages in enumerate(row['chat'])
        for message in messages
    }
    for row in source
}
report = json.load(open('data/beam-100k-dev-14-top300.json', encoding='utf-8'))
assert report['top_k'] == 300 and report['case_count'] == 84
by_category = {}
for row in report['rows']:
    ranked = row['ranked_message_ids']
    required = {int(item) for item in row['required_ranks']}
    batch_of = batch_by_conversation[row['conversation_id']]
    selected = ranked[:5]
    queues = {batch: [] for batch in set(batch_of.values())}
    for message_id in ranked[5:]:
        queues[batch_of[message_id]].append(message_id)
    while len(selected) < 100 and any(queues.values()):
        for batch in sorted(queues):
            if queues[batch] and len(selected) < 100:
                selected.append(queues[batch].pop(0))
    bucket = by_category.setdefault(row['category'], {'baseline': 0, 'candidate': 0, 'gain': 0, 'loss': 0})
    baseline = required <= set(ranked[:100])
    candidate = required <= set(selected)
    bucket['baseline'] += baseline
    bucket['candidate'] += candidate
    bucket['gain'] += candidate and not baseline
    bucket['loss'] += baseline and not candidate
print(json.dumps(by_category, indent=2))
