"""Import accepted PNGs from a successful public runner; never execute artifact code."""
from datetime import datetime, timezone
from pathlib import Path
import base64
import gzip
import hashlib
import io
import json
import os
import struct
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile

SOURCE = 'anicolao/e2e'
STORE = os.environ['GITHUB_REPOSITORY']
RUN = os.environ['SOURCE_RUN_ID']
PREFIX = 'evidence/runner-1/repeat-1/'
STORY = '/oracle-draw-reveals-and-lands-in-its-sorted-hand-layer/'

def require(condition, message):
    if not condition: raise RuntimeError(message)

def api(endpoint, method='GET', payload=None, file=None, mime=None):
    args = ['gh', 'api', '--method', method, endpoint]
    if mime: args += ['--header', 'Content-Type: ' + mime]
    if file: args += ['--input', str(file)]
    elif payload is not None: args += ['--input', '-']
    body = json.dumps(payload).encode() if payload is not None else None
    return json.loads(subprocess.check_output(args, input=body))

def public_bytes(url):
    with urllib.request.urlopen(url, timeout=60) as response: return response.read()

def digest(data): return 'sha256:' + hashlib.sha256(data).hexdigest()
def encoded(value): return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()

def upload(release, name, data, mime, directory):
    prior = next((asset for asset in release['assets'] if asset['name'] == name), None)
    if prior is None:
        path = directory / name; path.write_bytes(data)
        endpoint = f"https://uploads.github.com/repos/{STORE}/releases/{release['id']}/assets?name={name}"
        prior = api(endpoint, 'POST', file=path, mime=mime)
    require(prior['size'] == len(data) and prior['digest'] == digest(data), 'Uploaded bytes differ: ' + name)
    require(prior['content_type'] == mime, 'Wrong content type: ' + name)
    return prior

require(RUN.isdigit() and STORE == 'anicolao/e2e-baselines', 'Unexpected publication target')
run = api(f'repos/{SOURCE}/actions/runs/{RUN}')
require(run['conclusion'] == 'success' and run['event'] == 'workflow_dispatch' and run['head_branch'] == 'main', 'Source run must be a successful main-branch dispatch')
require(run['head_repository']['full_name'] == SOURCE and run['name'] == 'Pantheon byte repeatability', 'Unexpected source workflow')
revision = run['head_sha']
require(len(revision) == 40 and all(c in '0123456789abcdef' for c in revision), 'Invalid framework revision')
manifest_bytes = public_bytes(f'https://raw.githubusercontent.com/{SOURCE}/{revision}/poc/pantheon/baselines.json')
manifest = json.loads(manifest_bytes)
expected = {path: image for path, image in manifest['images'].items() if STORY in path and path.endswith('-linux.png')}
require(len(expected) == 6, 'Expected six checkpoint captures')
artifacts = api(f'repos/{SOURCE}/actions/runs/{RUN}/artifacts')['artifacts']
artifact = [item for item in artifacts if item['name'] == 'pantheon-seed-oracle-1' and not item['expired']]
require(len(artifact) == 1, 'Expected one seed artifact')
require(artifact[0]['size_in_bytes'] < sum(image['byteLength'] for image in expected.values()) + 16 * 1024 * 1024, 'Seed artifact exceeds its size budget')
base = api(f'repos/{STORE}/git/ref/heads/main')['object']['sha']
catalog = json.loads(public_bytes(f'https://raw.githubusercontent.com/{STORE}/{base}/catalog.json'))
require(catalog['schemaVersion'] == 1 and catalog['repository'] == STORE, 'Unexpected catalog')

with tempfile.TemporaryDirectory() as temporary:
    directory = Path(temporary)
    archive = directory / 'source.zip'
    with archive.open('wb') as output:
        subprocess.run(['gh', 'api', f"repos/{SOURCE}/actions/artifacts/{artifact[0]['id']}/zip"], stdout=output, check=True)
    objects = {}
    with zipfile.ZipFile(archive) as bundle:
        def read_member(name, limit):
            require(bundle.getinfo(name).file_size <= limit, 'Artifact member too large: ' + name)
            with bundle.open(name) as stream: data = stream.read(limit + 1)
            require(len(data) <= limit, 'Artifact member exceeds declared size')
            return data
        rows = [json.loads(line) for line in read_member(PREFIX + 'captures.jsonl', 1024 * 1024).decode().splitlines()]
        require(len(rows) == 6 and {row['baseline'] for row in rows} == set(expected), 'Incomplete capture set')
        report = json.loads(read_member(PREFIX + 'playwright.json', 4 * 1024 * 1024))
        require(report['stats']['expected'] == 3 and report['stats']['unexpected'] == 0 and report['stats']['skipped'] == 0 and report['stats']['flaky'] == 0 and not report['errors'], 'Source tests did not all pass')
        for row in rows:
            image = expected[row['baseline']]
            require(row['matches'] and row['mode'] == 'seed' and row['sourceCommit'] == manifest['source']['commit'], 'Unverified capture')
            data = read_member(PREFIX + 'objects/' + image['blobDigest'][7:] + '.png', image['byteLength'])
            require(len(data) == image['byteLength'] and digest(data) == image['blobDigest'], 'PNG integrity check failed')
            require(data[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', data[16:24]) == (image['width'], image['height']), 'Wrong PNG dimensions')
            objects[image['blobDigest']] = (image, data)
    missing = {key: value for key, value in objects.items() if key not in catalog['images']}
    for key, (image, _) in objects.items():
        if key in catalog['images']:
            require(all(catalog['images'][key][field] == image[field] for field in ['blobDigest', 'byteLength', 'width', 'height']), 'Existing catalog metadata differs')
    tag = 'seed-' + RUN
    release = None
    if missing:
        releases = api(f'repos/{STORE}/releases?per_page=100')
        release = next((item for item in releases if item['tag_name'] == tag), None)
        if release is None:
            release = api(f'repos/{STORE}/releases', 'POST', {'tag_name': tag, 'target_commitish': base, 'name': 'Runner-generated draw checkpoints', 'body': f'Imported original PNGs verified against accepted hashes in {SOURCE}@{revision}. Source run: {run["html_url"]}', 'draft': True})
        for key, (image, data) in missing.items():
            asset = upload(release, key[7:] + '.png', data, 'image/png', directory)
            catalog['images'][key] = {**image, 'release': tag, 'assetId': asset['id']}
        backup = io.BytesIO()
        with gzip.GzipFile(fileobj=backup, mode='wb', filename='', mtime=0) as compressor:
            with tarfile.open(fileobj=compressor, mode='w') as tar:
                for name, data in [(key[7:] + '.png', value[1]) for key, value in sorted(objects.items())] + [('manifest.json', encoded(expected))]:
                    entry = tarfile.TarInfo(name); entry.size = len(data); tar.addfile(entry, io.BytesIO(data))
        backup_bytes = backup.getvalue()
        upload(release, 'originals.tar.gz', backup_bytes, 'application/gzip', directory)
        if release['draft']: release = api(f"repos/{STORE}/releases/{release['id']}", 'PATCH', {'draft': False, 'make_latest': 'false'})
        require(release['immutable'], 'Release immutability is required')
        for key, (_, data) in missing.items():
            restored = public_bytes(f'https://github.com/{STORE}/releases/download/{tag}/{key[7:]}.png')
            require(digest(restored) == key, 'Public PNG audit failed')
        require(digest(public_bytes(f'https://github.com/{STORE}/releases/download/{tag}/originals.tar.gz')) == digest(backup_bytes), 'Public backup audit failed')
    receipt = {'schemaVersion': 1, 'sourceRun': run['html_url'], 'frameworkRevision': revision, 'sourceCommit': manifest['source']['commit'],
               'manifestDigest': digest(manifest_bytes), 'createdAt': datetime.now(timezone.utc).isoformat(), 'references': 6,
               'uniqueImages': len(objects), 'newImages': len(missing), 'reusedImages': len(objects) - len(missing),
               'verifiedBytes': sum(len(data) for _, data in objects.values()), 'catalogParent': base,
               'release': f'https://github.com/{STORE}/releases/tag/{tag}' if missing else None}
    # Single-writer workflow plus a fast-forward-only update keeps concurrent edits intact.
    files = {'catalog.json': encoded(catalog), f'publications/{RUN}.json': encoded(receipt)}
    entries = []
    for path, data in files.items():
        blob = api(f'repos/{STORE}/git/blobs', 'POST', {'content': base64.b64encode(data).decode(), 'encoding': 'base64'})
        entries.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
    tree = api(f'repos/{STORE}/git/trees', 'POST', {'base_tree': api(f'repos/{STORE}/git/commits/{base}')['tree']['sha'], 'tree': entries})
    commit = api(f'repos/{STORE}/git/commits', 'POST', {'message': f'Import verified PNGs from runner {RUN}', 'tree': tree['sha'], 'parents': [base]})
    api(f'repos/{STORE}/git/refs/heads/main', 'PATCH', {'sha': commit['sha'], 'force': False})
    receipt['catalogRevision'] = commit['sha']; receipt['catalogDigest'] = digest(files['catalog.json'])
    print(json.dumps(receipt, indent=2))
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
        summary.write(f"Imported {len(missing)} new PNGs, reused {len(objects) - len(missing)}. Verified {receipt['verifiedBytes']:,} bytes.\n\nCatalog: `{commit['sha']}`\n")
