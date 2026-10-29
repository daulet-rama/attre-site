"""Поддельный GitHub для httpx.MockTransport: refs, коммиты, деревья, blobs и прогоны Actions в памяти.

Ведёт себя как настоящий там, где это важно админке: удаление несуществующего пути в дереве — 422,
PATCH ref не «вперёд» — 422 «Update is not a fast forward», проверяет обязательные заголовки.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import threading

import httpx

from app.store import git_blob_sha

TOKEN = 'test-token-not-real'


class FakeGitHub:
    def __init__(self, files: dict[str, bytes], repo: str = 'owner/attre-site', branch: str = 'main'):
        self.repo, self.branch = repo, branch
        self.blobs: dict[str, bytes] = {}
        self.trees: dict[str, dict[str, str]] = {}
        self.commits: dict[str, dict] = {}
        self.requests: list[tuple[str, str, dict | None]] = []
        self.bad_headers: list[str] = []
        self.runs: list[dict] = []
        self.race_on_patch = 0           # столько раз PATCH ref «проиграет гонку»: кто-то запушит раньше
        self.lose_patch_response = 0     # столько раз PATCH ref применится, но ответ «не дойдёт» (таймаут)
        self.timeout_patch = 0           # столько раз PATCH ref оборвётся таймаутом, НЕ применившись
        self.refuse_patch = 0            # столько раз PATCH ref получит 422 без движения ветки (защита ветки)
        self.blob_rate_limit = 0         # столько POST blobs получат 403 «вторичный лимит» с Retry-After
        self.ref_gate: threading.Event | None = None   # GET ref ждёт, пока событие не выставят (медленный GitHub)
        self.fail_next: list[httpx.Response | Exception] = []
        self._lock = threading.Lock()
        tree = {p: self._put_blob(d) for p, d in files.items()}
        self.refs = {branch: self._commit(self._put_tree(tree), [], 'начало', 'Тест')}

    def count(self, method: str, suffix: str) -> int:
        return sum(1 for m, p, _ in list(self.requests) if m == method and p.endswith(suffix))

    # ——— «git» в памяти ———
    def _put_blob(self, data: bytes) -> str:
        sha = git_blob_sha(data)
        self.blobs[sha] = data
        return sha

    def _put_tree(self, tree: dict[str, str]) -> str:
        sha = hashlib.sha1(json.dumps(sorted(tree.items())).encode()).hexdigest()
        self.trees[sha] = dict(tree)
        return sha

    def _commit(self, tree: str, parents: list[str], message: str, author: str) -> str:
        sha = hashlib.sha1(f'{tree}{parents}{message}{len(self.commits)}'.encode()).hexdigest()
        self.commits[sha] = {'tree': tree, 'parents': parents, 'message': message, 'author': author}
        return sha

    def files(self, ref: str | None = None) -> dict[str, bytes]:
        tree = self.trees[self.commits[ref or self.refs[self.branch]]['tree']]
        return {p: self.blobs[s] for p, s in tree.items()}

    def head(self) -> str:
        return self.refs[self.branch]

    def push_external(self, path: str, data: bytes | None, message: str = 'чужой коммит') -> str:
        """Коммит «с другого компьютера» прямо в ветку."""
        head = self.head()
        tree = dict(self.trees[self.commits[head]['tree']])
        if data is None:
            tree.pop(path, None)
        else:
            tree[path] = self._put_blob(data)
        sha = self._commit(self._put_tree(tree), [head], message, 'Даулет')
        self.refs[self.branch] = sha
        return sha

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    # ——— HTTP ———
    def handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        path = request.url.path
        self.requests.append((request.method, path, body))
        for name, value in (('authorization', f'Bearer {TOKEN}'), ('accept', 'application/vnd.github+json'),
                            ('x-github-api-version', '2022-11-28')):
            if request.headers.get(name) != value:
                self.bad_headers.append(f'{request.method} {path}: {name}')
        r = f'/repos/{self.repo}'
        rest = path[len(r):] if path.startswith(r) else ''
        m = request.method
        if m == 'GET' and rest == f'/git/ref/heads/{self.branch}' and self.ref_gate is not None:
            self.ref_gate.wait(10)
        with self._lock:
            return self._handle(request, body, path, rest, m)

    def _handle(self, request, body, path, rest, m) -> httpx.Response:
        if self.fail_next:
            item = self.fail_next.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        r = f'/repos/{self.repo}'
        if not path.startswith(r):
            return httpx.Response(404, json={'message': 'Not Found'})

        if m == 'GET' and rest == f'/git/ref/heads/{self.branch}':
            return httpx.Response(200, json={'ref': f'refs/heads/{self.branch}',
                                             'object': {'sha': self.head(), 'type': 'commit'}})
        if m == 'GET' and (mm := re.fullmatch(r'/git/commits/([0-9a-f]{40})', rest)):
            c = self.commits.get(mm.group(1))
            if not c:
                return httpx.Response(404, json={'message': 'Not Found'})
            return httpx.Response(200, json={'sha': mm.group(1), 'tree': {'sha': c['tree']},
                                             'parents': [{'sha': p} for p in c['parents']], 'message': c['message']})
        if m == 'GET' and (mm := re.fullmatch(r'/git/trees/([0-9a-f]{40})', rest)):
            tree = self.trees.get(mm.group(1))
            if tree is None:
                return httpx.Response(404, json={'message': 'Not Found'})
            dirs = sorted({'/'.join(p.split('/')[:i]) for p in tree for i in range(1, p.count('/') + 1)})
            entries = [{'path': d, 'mode': '040000', 'type': 'tree', 'sha': '0' * 40} for d in dirs]
            entries += [{'path': p, 'mode': '100644', 'type': 'blob', 'sha': s, 'size': len(self.blobs[s])}
                        for p, s in sorted(tree.items())]
            return httpx.Response(200, json={'sha': mm.group(1), 'tree': entries, 'truncated': False})
        if m == 'GET' and (mm := re.fullmatch(r'/git/blobs/([0-9a-f]{40})', rest)):
            data = self.blobs.get(mm.group(1))
            if data is None:
                return httpx.Response(404, json={'message': 'Not Found'})
            b64 = base64.b64encode(data).decode()
            b64 = '\n'.join(b64[i:i + 60] for i in range(0, len(b64), 60)) + '\n'   # как у GitHub — с переносами
            return httpx.Response(200, json={'sha': mm.group(1), 'size': len(data), 'content': b64,
                                             'encoding': 'base64'})
        if m == 'POST' and rest == '/git/blobs':
            assert body['encoding'] == 'base64'
            if self.blob_rate_limit:
                self.blob_rate_limit -= 1
                return httpx.Response(403, json={'message': 'You have exceeded a secondary rate limit.'},
                                      headers={'retry-after': '2'})
            return httpx.Response(201, json={'sha': self._put_blob(base64.b64decode(body['content']))})
        if m == 'POST' and rest == '/git/trees':
            base = self.trees.get(body.get('base_tree'))
            if base is None:
                return httpx.Response(422, json={'message': 'Invalid base_tree'})
            tree = dict(base)
            for e in body['tree']:
                if 'sha' in e and e['sha'] is None:
                    if e['path'] not in tree:
                        return httpx.Response(422, json={'message': 'GitRPC::BadObjectState'})
                    tree.pop(e['path'])
                elif 'content' in e:
                    tree[e['path']] = self._put_blob(e['content'].encode('utf-8'))
                elif e.get('sha') in self.blobs:
                    tree[e['path']] = e['sha']
                else:
                    return httpx.Response(422, json={'message': 'tree.sha is not a valid blob'})
            return httpx.Response(201, json={'sha': self._put_tree(tree)})
        if m == 'POST' and rest == '/git/commits':
            if body['tree'] not in self.trees or any(p not in self.commits for p in body['parents']):
                return httpx.Response(422, json={'message': 'Invalid tree or parent'})
            sha = self._commit(body['tree'], body['parents'], body['message'], body.get('author', {}).get('name'))
            return httpx.Response(201, json={'sha': sha})
        if m == 'PATCH' and rest == f'/git/refs/heads/{self.branch}':
            if self.race_on_patch:
                self.race_on_patch -= 1
                self.push_external('data/race.json', b'{"race": %d}\n' % self.race_on_patch)
                return httpx.Response(422, json={'message': 'Update is not a fast forward'})
            if self.timeout_patch:
                self.timeout_patch -= 1
                raise httpx.ReadTimeout('нет ответа')
            if self.refuse_patch:
                self.refuse_patch -= 1
                return httpx.Response(422, json={'message': 'Protected branch update failed for refs/heads/main.'})
            commit = self.commits.get(body['sha'])
            if not commit or (self.head() not in commit['parents'] and not body.get('force')):
                return httpx.Response(422, json={'message': 'Update is not a fast forward'})
            self.refs[self.branch] = body['sha']
            if self.lose_patch_response:                 # записали, а ответ до админки не дошёл
                self.lose_patch_response -= 1
                raise httpx.ReadTimeout('ответ потерян')
            return httpx.Response(200, json={'ref': f'refs/heads/{self.branch}', 'object': {'sha': body['sha']}})
        if m == 'GET' and rest == '/actions/runs':
            return httpx.Response(200, json={'total_count': len(self.runs), 'workflow_runs': self.runs})
        return httpx.Response(404, json={'message': 'Not Found'})
