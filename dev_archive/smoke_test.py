import os, uuid
from app import app

client = app.test_client()
username = 'smokecand_' + uuid.uuid4().hex[:8]
data = dict(name='Smoke Cand', email=f'{username}@example.com', username=username, password='pass', category='General')
r = client.post('/candidate_signup', data=data, follow_redirects=True)
print('POST /candidate_signup ->', r.status_code, 'username=', username)
