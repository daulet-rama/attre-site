"""Хранилище: LocalStore на временном git-репозитории, GitHubStore — на поддельном GitHub (httpx.MockTransport)."""
from __future__ import annotations

import threading
import time

import httpx
import pytest

from app.store import (MSG_BUSY, MSG_DOWN, MSG_RATE, MSG_REFUSED, MSG_TOKEN, ConflictError, GitHubStore, LocalStore,
                       StoreError, check_path, git_blob_sha)
from conftest import first_photo, git
from fake_github import TOKEN, FakeGitHub


# ——————————————————————————— общее ———————————————————————————

def test_git_blob_sha_matches_git(repo):
    data = (repo / 'data' / 'settings.json').read_bytes()
    assert git_blob_sha(data) == git(repo, 'hash-object', 'data/settings.json')


@pytest.mark.parametrize('bad', ['../x', '/etc/passwd', 'data/../x', 'data//x', 'src/app.js', 'data\\x', 'admin/a.py',
                                 'data/./x', '', 'build.py', 'core.py', '.github/workflows/pages.yml',
                                 'data/colors.json', 'data/home.json', 'data/categories/bags.json', 'media/home/a.jpg',
                                 'data/products/ALTEA.json', 'data/products/x/y.json', 'media/products/a.gif',
                                 'media/products/../../build.py'])
def test_check_path_rejects(bad):
    """Только товары, настройки, тексты сайта и фото товаров — палитру, главную и код сайта админка не пишет."""
    with pytest.raises(ValueError):
        check_path(bad)


def test_check_path_ok():
    assert check_path('data/products/altea.json') == 'data/products/altea.json'
    for ok in ('media/products/a-b-1.jpg', 'media/products/IMG_1.JPG', 'data/settings.json', 'data/i18n.json',
               'data/products/siena-mini-2.json'):
        assert check_path(ok) == ok


# ——————————————————————————— LocalStore ———————————————————————————

def test_local_read_list(repo):
    st = LocalStore(repo)
    assert st.head() == git(repo, 'rev-parse', 'HEAD')
    products = st.list('data/products/')
    assert 'data/products/altea.json' in products and len(products) >= 40
    assert all(p.startswith('data/products/') for p in products)
    assert st.read('data/products/altea.json') == (repo / 'data/products/altea.json').read_bytes()
    assert st.blob_sha('data/products/altea.json') == git(repo, 'hash-object', 'data/products/altea.json')
    assert st.read('data/products/nope.json') is None and st.blob_sha('data/products/nope.json') is None


def test_local_commit_add_change_delete(repo):
    st = LocalStore(repo)
    before = st.head()
    photo = first_photo(repo, 'altea')
    sha = st.commit({'data/products/zz.json': b'{"a": 1}\n', 'data/settings.json': b'{}\n',
                     photo: None}, 'Админка: тест (Дамира)', 'Дамира')
    assert sha != before and sha == git(repo, 'rev-parse', 'HEAD')
    assert git(repo, 'log', '-1', '--format=%an <%ae>|%s') == 'Дамира <admin@attre.local>|Админка: тест (Дамира)'
    assert git(repo, 'rev-parse', 'HEAD~1') == before
    names = git(repo, 'show', '--name-status', '--format=', 'HEAD').splitlines()
    assert sorted(names) == ['A\tdata/products/zz.json', f'D\t{photo}', 'M\tdata/settings.json']
    assert not (repo / photo).exists()
    assert (repo / 'data/products/zz.json').read_bytes() == b'{"a": 1}\n'
    assert git(repo, 'status', '--porcelain') == ''
    assert st.read('data/products/zz.json') == b'{"a": 1}\n' and st.blob_sha(photo) is None
    assert st.last_commit == sha


def test_local_commit_only_given_paths(repo):
    """Чужие изменения в рабочей копии (даже подготовленные к коммиту) в коммит админки не попадают."""
    (repo / 'README.md').write_text('чужая правка\n', encoding='utf-8')
    git(repo, 'add', 'README.md')
    st = LocalStore(repo)
    st.commit({'data/products/zz.json': b'{}\n'}, 'тест', 'Жанна')
    assert git(repo, 'show', '--name-only', '--format=', 'HEAD') == 'data/products/zz.json'
    assert 'README.md' in git(repo, 'status', '--porcelain')


def test_local_noop_and_expect(repo):
    st = LocalStore(repo)
    head = st.head()
    same = (repo / 'data/settings.json').read_bytes()
    assert st.commit({'data/settings.json': same, 'data/products/none.json': None}, 'ничего', 'Дамира') == head
    assert st.last_commit is None                       # пустой «коммит» — не коммит админки
    sha = st.blob_sha('data/settings.json')
    with pytest.raises(ConflictError):
        st.commit({'data/settings.json': b'{}\n'}, 'x', 'Дамира', expect={'data/settings.json': 'f' * 40})
    with pytest.raises(ConflictError):
        st.commit({'data/products/altea.json': b'{}\n'}, 'x', 'Дамира', expect={'data/products/altea.json': None})
    assert st.head() == head
    st.commit({'data/settings.json': b'{}\n'}, 'x', 'Дамира', expect={'data/settings.json': sha})
    assert st.head() != head


def test_local_commit_refuses_outside_data(repo):
    st = LocalStore(repo)
    with pytest.raises(ValueError):
        st.commit({'admin/app/main.py': b'x'}, 'x', 'Дамира')
    with pytest.raises(ValueError):
        st.commit({'data/../build.py': b'x'}, 'x', 'Дамира')


def test_local_author_cleaned(repo):
    st = LocalStore(repo)
    st.commit({'data/products/zz.json': b'{}\n'}, 'x', 'Злой <evil@x>\nимя')
    assert git(repo, 'log', '-1', '--format=%an|%ae') == 'Злой evil@xимя|admin@attre.local'


# ——————————————————————————— GitHubStore ———————————————————————————

FILES = {
    'data/products/altea.json': b'{"id": "001"}\n',
    'data/products/bergen.json': b'{"id": "002"}\n',
    'data/settings.json': b'{"whatsapp": "77000000000"}\n',
    'media/products/altea-1.jpg': b'\xff\xd8 jpeg 1',
    'media/products/altea-2.jpg': b'\xff\xd8 jpeg 2',
    'build.py': b'print(1)\n',
}


def gh_store(fake: FakeGitHub, **kw) -> GitHubStore:
    return GitHubStore(TOKEN, fake.repo, fake.branch, transport=fake.transport(), sleep=lambda s: None, **kw)


def test_github_read_tree_and_file():
    fake = FakeGitHub(FILES)
    st = gh_store(fake)
    assert st.head() == fake.head()
    assert st.list('data/products/') == {p: git_blob_sha(d) for p, d in FILES.items() if p.startswith('data/products/')}
    assert st.read('data/products/altea.json') == FILES['data/products/altea.json']
    assert st.read('media/products/altea-2.jpg') == FILES['media/products/altea-2.jpg']
    assert st.read('data/nope.json') is None
    assert st.blob_sha('data/settings.json') == git_blob_sha(FILES['data/settings.json'])
    many = st.snapshot().read_many(['data/products/altea.json', 'data/products/bergen.json', 'data/x.json'])
    assert many == {'data/products/altea.json': FILES['data/products/altea.json'],
                    'data/products/bergen.json': FILES['data/products/bergen.json'], 'data/x.json': None}
    assert not fake.bad_headers
    # дерево запрошено рекурсивно, содержимое — через blobs
    assert any(m == 'GET' and '/git/trees/' in p for m, p, _ in fake.requests)
    assert any(m == 'GET' and '/git/blobs/' in p for m, p, _ in fake.requests)


def test_github_cache():
    fake = FakeGitHub(FILES)
    st = gh_store(fake)
    st.read('data/products/altea.json')
    n = len(fake.requests)
    st.read('data/products/altea.json')
    st.list('data/')
    assert len(fake.requests) == n            # голова ветки, дерево и файл — из кэша
    st.snapshot(fresh=True)
    assert len(fake.requests) == n + 1        # свежая голова — один запрос ref, дерево того же коммита — из кэша


def test_github_commit_with_delete():
    fake = FakeGitHub(FILES)
    st = gh_store(fake)
    old = fake.head()
    jpeg = b'\xff\xd8 new photo'
    sha = st.commit({'data/products/altea.json': b'{"id": "001", "x": "\xd1\x8f"}\n',
                     'media/products/altea-black-abc123.jpg': jpeg,
                     'media/products/altea-1.jpg': None, 'media/products/never-existed.jpg': None},
                    'Админка: «Altea» — сохранено (Дамира)', 'Дамира')
    assert sha == fake.head() != old
    commit = fake.commits[sha]
    assert commit['parents'] == [old] and commit['message'] == 'Админка: «Altea» — сохранено (Дамира)'
    assert commit['author'] == 'Дамира'
    files = fake.files()
    assert 'media/products/altea-1.jpg' not in files
    assert files['media/products/altea-black-abc123.jpg'] == jpeg
    assert files['data/products/altea.json'] == '{"id": "001", "x": "я"}\n'.encode()
    assert files['build.py'] == FILES['build.py']                      # остальное — из base_tree
    tree_req = next(b for m, p, b in fake.requests if m == 'POST' and p.endswith('/git/trees'))
    assert tree_req['base_tree'] == fake.commits[old]['tree']
    entries = {e['path']: e for e in tree_req['tree']}
    assert entries['media/products/altea-1.jpg']['sha'] is None         # удаление = sha: null
    assert 'media/products/never-existed.jpg' not in entries           # удалять несуществующее GitHub не даёт
    assert 'sha' in entries['media/products/altea-black-abc123.jpg']    # фото — заранее созданным blob
    assert any(m == 'POST' and p.endswith('/git/blobs') for m, p, _ in fake.requests)
    patch = [b for m, p, b in fake.requests if m == 'PATCH']
    assert patch == [{'sha': sha, 'force': False}]
    assert st.read('data/products/altea.json') == files['data/products/altea.json']   # кэш сброшен
    assert st.last_commit == sha and not fake.bad_headers


def test_github_commit_retries_when_branch_moved():
    fake = FakeGitHub(FILES)
    st = gh_store(fake)
    st.head()
    fake.race_on_patch = 2
    sha = st.commit({'data/products/bergen.json': b'{"id": "002", "new": true}\n'}, 'msg', 'Жанна')
    assert sha == fake.head()
    patches = [b for m, p, b in fake.requests if m == 'PATCH']
    assert len(patches) == 3
    files = fake.files()
    assert files['data/race.json'] == b'{"race": 0}\n'                  # чужой коммит не потерян
    assert files['data/products/bergen.json'] == b'{"id": "002", "new": true}\n'
    assert fake.commits[fake.commits[sha]['parents'][0]]['message'] == 'чужой коммит'


def test_github_commit_gives_up_after_three_races():
    fake = FakeGitHub(FILES)
    st = gh_store(fake)
    fake.race_on_patch = 5
    with pytest.raises(StoreError) as ex:
        st.commit({'data/products/bergen.json': b'{}\n'}, 'msg', 'Жанна')
    assert ex.value.message == MSG_BUSY
    assert sum(1 for m, *_ in fake.requests if m == 'PATCH') == 3


def test_github_expect_conflict_after_external_push():
    fake = FakeGitHub(FILES)
    st = gh_store(fake)
    snap = st.snapshot()
    fake.push_external('data/products/altea.json', b'{"id": "001", "by": "other"}\n')
    with pytest.raises(ConflictError):
        st.commit({'data/products/altea.json': b'{}\n'}, 'msg', 'Дамира',
                  expect={'data/products/altea.json': snap.blob_sha('data/products/altea.json')})
    assert fake.files()['data/products/altea.json'] == b'{"id": "001", "by": "other"}\n'


def test_github_noop_commit_makes_no_requests_to_write():
    fake = FakeGitHub(FILES)
    st = gh_store(fake)
    head = st.commit({'data/settings.json': FILES['data/settings.json'], 'data/products/none.json': None}, 'msg',
                     'Дамира')
    assert head == fake.head()
    assert not any(m in ('POST', 'PATCH') for m, *_ in fake.requests)


@pytest.mark.parametrize('failure, message', [
    (httpx.ConnectTimeout('timeout'), MSG_DOWN),
    (httpx.ConnectError('down'), MSG_DOWN),
    (httpx.Response(401, json={'message': 'Bad credentials'}), MSG_TOKEN),
    (httpx.Response(403, json={'message': 'API rate limit exceeded'}, headers={'x-ratelimit-remaining': '0'}),
     MSG_RATE),
    (httpx.Response(502, json={'message': 'Server Error'}), MSG_DOWN),
])
def test_github_errors_are_human(failure, message):
    fake = FakeGitHub(FILES)
    st = gh_store(fake)
    fake.fail_next = [failure, failure]            # чтение повторяется один раз — оба раза сбой
    with pytest.raises(StoreError) as ex:
        st.head()
    assert ex.value.message == message
    assert TOKEN not in ex.value.message


def test_github_get_retried_once():
    fake = FakeGitHub(FILES)
    st = gh_store(fake)
    fake.fail_next = [httpx.ReadTimeout('slow')]
    assert st.head() == fake.head()


def run(head_sha, status, conclusion=None, created='2026-10-28T10:00:00Z'):
    return {'head_sha': head_sha, 'status': status, 'conclusion': conclusion, 'html_url': f'https://x/{head_sha[:6]}',
            'created_at': created, 'run_started_at': created, 'updated_at': '2026-10-28T10:02:00Z'}


def test_github_publish_status():
    fake = FakeGitHub(FILES)
    st = gh_store(fake, status_ttl=0)
    assert st.publish_status()['state'] == 'unknown'                 # прогонов нет и админка ничего не сохраняла
    fake.runs = [run(fake.head(), 'completed', 'success')]
    assert st.publish_status()['state'] == 'done'                    # после перезапуска — по последнему прогону
    sha = st.commit({'data/products/altea.json': b'{}\n'}, 'msg', 'Дамира')
    s = st.publish_status()
    assert s['state'] == 'queued' and s['commit'] == sha             # Actions ещё не завёл прогон
    fake.runs.insert(0, run(sha, 'queued', created='2026-10-28T10:05:00Z'))
    assert st.publish_status()['state'] == 'queued'
    fake.runs[0] = run(sha, 'in_progress', created='2026-10-28T10:05:00Z')
    assert st.publish_status()['state'] == 'building'
    fake.runs[0] = run(sha, 'completed', 'success', created='2026-10-28T10:05:00Z')
    s = st.publish_status()
    assert s['state'] == 'done' and s['url'] == f'https://x/{sha[:6]}' and s['finished']
    fake.runs[0] = run(sha, 'completed', 'failure', created='2026-10-28T10:05:00Z')
    assert st.publish_status()['state'] == 'failed'
    # прогон отменён, потому что за ним пришёл новый — смотрим на новый
    fake.runs[0] = run(sha, 'completed', 'cancelled', created='2026-10-28T10:05:00Z')
    fake.runs.insert(0, run('e' * 40, 'in_progress', created='2026-10-28T10:06:00Z'))
    assert st.publish_status()['state'] == 'building'
    req = [p for m, p, _ in fake.requests if p.endswith('/actions/runs')]
    assert req and not fake.bad_headers


def test_github_publish_status_prefers_pages_workflow():
    fake = FakeGitHub(FILES)
    st = gh_store(fake, status_ttl=0)
    sha = st.commit({'data/products/altea.json': b'{}\n'}, 'msg', 'Дамира')
    fake.runs = [{**run(sha, 'completed', 'failure', created='2026-10-28T10:06:00Z'), 'name': 'tests',
                  'path': '.github/workflows/tests.yml'},
                 {**run(sha, 'completed', 'success'), 'name': 'pages', 'path': '.github/workflows/pages.yml'}]
    assert st.publish_status()['state'] == 'done'


def test_github_publish_status_survives_errors():
    fake = FakeGitHub(FILES)
    st = gh_store(fake, status_ttl=0)
    fake.fail_next = [httpx.Response(403, json={'message': 'Resource not accessible'})]
    assert st.publish_status()['state'] == 'unknown'


def test_github_head_one_request_for_all():
    """Пачка запросов разом (миниатюры списка) при устаревшей голове ветки — к GitHub уходит один запрос."""
    fake = FakeGitHub(FILES)
    st = gh_store(fake, head_ttl=0.05)
    first = st.head()
    time.sleep(0.1)
    fake.ref_gate = threading.Event()
    got = []
    threads = [threading.Thread(target=lambda: got.append(st.head())) for _ in range(20)]
    for t in threads:
        t.start()
    time.sleep(0.3)
    fake.ref_gate.set()
    for t in threads:
        t.join(5)
    assert got == [first] * 20
    assert fake.count('GET', '/git/ref/heads/main') == 2               # первый вызов + один на все двадцать


def test_github_head_stale_on_error_for_reads_only():
    """GitHub не ответил: чтение получает последнюю известную голову (список и фото из кэша открываются),
    запись (fresh) — ошибку: сохранять по устаревшей голове нельзя."""
    fake = FakeGitHub(FILES)
    st = gh_store(fake, head_ttl=0)
    head = st.head()
    fake.fail_next = [httpx.ConnectError('down')] * 4
    assert st.head() == head
    with pytest.raises(StoreError) as ex:
        st.head(fresh=True)
    assert ex.value.message == MSG_DOWN


def test_github_blob_secondary_rate_limit_waits_once():
    fake = FakeGitHub(FILES)
    slept = []
    st = GitHubStore(TOKEN, fake.repo, fake.branch, transport=fake.transport(), sleep=slept.append)
    fake.blob_rate_limit = 1
    sha = st.commit({'media/products/altea-x-aaaaaa.jpg': b'\xff\xd8 photo'}, 'msg', 'Дамира')
    assert sha == fake.head() and 2 in slept
    assert fake.count('POST', '/git/blobs') == 2


def test_github_patch_applied_but_response_lost():
    """Ответ на запись ветки потерян, но GitHub её применил — это успех, а не «GitHub не отвечает»."""
    fake = FakeGitHub(FILES)
    st = gh_store(fake)
    old = fake.head()
    fake.lose_patch_response = 1
    sha = st.commit({'data/products/altea.json': b'{"id": "001", "price": 1}\n'}, 'msg', 'Дамира')
    assert sha == fake.head() != old and st.last_commit == sha
    assert fake.count('PATCH', '/git/refs/heads/main') == 1            # повторной записи не было


def test_github_patch_timeout_not_applied_is_an_error():
    fake = FakeGitHub(FILES)
    st = gh_store(fake)
    old = fake.head()
    fake.timeout_patch = 1
    with pytest.raises(StoreError) as ex:
        st.commit({'data/products/altea.json': b'{}\n'}, 'msg', 'Дамира')
    assert ex.value.message == MSG_DOWN and fake.head() == old and st.last_commit is None


def test_github_refused_patch_not_a_race():
    """422, а ветка на месте (защита ветки): не повторяем трижды, а сразу просим сообщить Даулету."""
    fake = FakeGitHub(FILES)
    st = gh_store(fake)
    fake.refuse_patch = 3
    with pytest.raises(StoreError) as ex:
        st.commit({'data/products/altea.json': b'{}\n'}, 'msg', 'Дамира')
    assert ex.value.message == MSG_REFUSED
    assert fake.count('PATCH', '/git/refs/heads/main') == 1


def test_github_create_objects_retried_once_on_5xx():
    """blobs / trees / commits — без побочных эффектов: при 5xx повторяем один раз; запись ветки — нет."""
    fake = FakeGitHub(FILES)
    st = gh_store(fake)
    st.head()
    st.snapshot()
    real = fake.handle
    failed = []

    def flaky(request):
        if request.method == 'POST' and request.url.path.endswith('/git/trees') and not failed:
            failed.append(1)
            return httpx.Response(502, json={'message': 'Server Error'})
        return real(request)

    st._client._transport = httpx.MockTransport(flaky)
    sha = st.commit({'data/products/altea.json': b'{"id": "001", "x": 1}\n'}, 'msg', 'Дамира')
    assert sha == fake.head() and failed
