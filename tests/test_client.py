"""Offline standalone client regression; no private imports or payment provider."""
import base64
import copy
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/ziyou-mhxy-assistant-paid'
sys.path.insert(0, str(ROOT / 'tools'))
from verify_client import verify
from build_client import build

spec = importlib.util.spec_from_file_location('standalone_remote', SKILL / 'scripts/remote_client.py')
remote = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = remote
spec.loader.exec_module(remote)


@contextmanager
def response(status=200, headers=(), data=None):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass
        def do_POST(self):
            body = self.rfile.read(int(self.headers['Content-Length']))
            requests.append((self.path, body, dict(self.headers)))
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            for key, value in headers:
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(json.dumps(data or {}).encode())
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:' + str(server.server_port), requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


class ClientTests(unittest.TestCase):
    def test_manifest_and_private_boundary(self):
        result = verify()
        self.assertEqual(result['preserved_runtime_files'], 16)
        self.assertEqual(result['discoverable_skills'], 1)

    def test_free_calculation_from_unrelated_directory_isolated_python(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable, '-I', '-X', 'utf8', '-B', str(SKILL / 'basic/scripts/resources.py'),
                                     str(SKILL / 'basic/examples/cultivation-input.json'), '--kind', 'cultivation'],
                                    cwd=temp, capture_output=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsInstance(json.loads(result.stdout), dict)
        self.assertNotIn('Payment-Proof', result.stdout)

    def test_remote_cli_and_free_dependencies_are_self_contained(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable, '-I', '-X', 'utf8', '-B', str(SKILL / 'scripts/remote_client.py'), '--help'],
                                    cwd=temp, capture_output=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(callable(remote.free_dossier()._bounded))
        self.assertTrue(callable(remote.free_asset_draft().create))

    def test_only_explicit_loopback_can_use_plain_http(self):
        for url in ('http://example.com', 'http://127.0.0.1', 'https://example.com/path',
                    'https://name:secret@example.com', 'https://example.com?token=secret'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                remote.RemoteClient(url)
        remote.RemoteClient('http://127.0.0.1', allow_localhost=True)

    def test_original_post_and_bill_are_passed_unchanged_without_payment(self):
        payload = {'service': remote.SERVICE, 'draft_id': 'a' * 32, 'revision': 1}
        with response(402, [('Payment-Needed', 'synthetic-bill')], {'code': 'PAYMENT_REQUIRED'}) as (url, requests):
            client = remote.RemoteClient(url, allow_localhost=True)
            result = client.post('/v1/scenario-confirmed-calculate', payload)
            client.profile = {'synthetic': True}
            result = remote.official_payment_request(result, client, '/v1/scenario-confirmed-calculate', payload)
        self.assertEqual(result['payment_needed'], 'synthetic-bill')
        self.assertEqual(len(requests), 1)
        self.assertEqual(result['payment_request']['data'], remote.canonical(payload))
        self.assertEqual(requests[0][1], result['payment_request']['data'].encode())
        self.assertEqual(result['payment_request']['method'], 'POST')
        self.assertNotIn('Payment-Proof', requests[0][2])

    def test_redirect_and_duplicate_bill_headers_are_rejected(self):
        cases = [(302, [('Location', 'https://example.com')], 'REDIRECT_REFUSED'),
                 (402, [('Payment-Needed', 'a'), ('Payment-Needed', 'b')], 'INVALID_BILL_HEADER')]
        for status, headers, code in cases:
            with response(status, headers) as (url, _):
                with self.assertRaises(remote.RemoteError) as error:
                    remote.RemoteClient(url, allow_localhost=True).post('/v1/scenario-prepare', {})
            self.assertEqual(error.exception.code, code)

    def test_free_prepare_never_accepts_a_payment_proof(self):
        proof = base64.urlsafe_b64encode(json.dumps({'protocol': {'trade_no': 'synthetic',
                    'payment_proof': 'synthetic'}, 'method': {}}).encode()).decode()
        client = remote.RemoteClient('http://127.0.0.1', allow_localhost=True)
        with patch.object(remote.http.client.HTTPConnection, 'request', side_effect=AssertionError('No network')):
            with self.assertRaises(ValueError):
                client.post('/v1/asset-prepare', {}, proof=proof)
            with self.assertRaises(remote.RemoteError):
                client.post('/v1/asset-confirmed-calculate', {}, proof='bad\r\nproof')

    def test_partial_asset_create_reopen_inspect_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            facts = Path(temp) / 'facts.json'
            command = [sys.executable, '-I', '-X', 'utf8', '-B', str(SKILL / 'scripts/remote_client.py')]
            created = subprocess.run(command + ['asset-create', '--output', str(facts)],
                input=json.dumps({'request': {'input': {'budget': None}}, 'source': '合成缺项资料'}),
                cwd=temp, capture_output=True, encoding='utf-8', timeout=20)
            self.assertEqual(created.returncode, 0, created.stderr + created.stdout)
            report = json.loads(created.stdout)
            self.assertFalse(report['charge_created'])
            self.assertFalse(report['analysis_returned'])
            self.assertEqual(report['draft']['request']['input']['budget'], None)
            before = facts.read_bytes()
            for action in ('asset-load', 'asset-inspect'):
                result = subprocess.run(command + [action, '--workspace', str(facts)],
                    cwd=temp, capture_output=True, encoding='utf-8', timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertFalse(json.loads(result.stdout)['charge_created'])
            failed = subprocess.run(command + ['asset-create', '--output', str(facts)],
                input='{}', cwd=temp, capture_output=True, encoding='utf-8', timeout=20)
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(facts.read_bytes(), before)
            self.assertNotIn(b'Payment-Proof', before)

    def test_synthetic_delivery_requires_original_order_binding_and_fulfillment(self):
        def encode(value):
            return base64.urlsafe_b64encode(json.dumps(value).encode()).decode()
        binding = dict(service=remote.SERVICE, draft_id='d' * 32, revision=1,
                       confirmation_hash='a' * 64, input_summary_hash='b' * 64)
        receipt = dict(validated=True, trade_no='synthetic-only', out_trade_no='e' * 32, resource_id='f' * 32)
        quote = dict(http_status=402, payment_needed=encode({'protocol': dict(
            resource_id=receipt['resource_id'], out_trade_no=receipt['out_trade_no'], amount='0.10', currency='CNY')}),
            data=dict(code='PAYMENT_REQUIRED', amount='0.10', currency='CNY', resource_id=receipt['resource_id'],
                      confirmation_binding=binding))
        proof = encode({'protocol': {'trade_no': receipt['trade_no'], 'payment_proof': 'synthetic-only'}, 'method': {}})
        good = dict(http_status=200, payment_validation=encode(receipt),
                    data=dict(receipt, confirmation_binding=binding, fulfillment_confirmed=True, content={'synthetic_only': True}))
        self.assertEqual(remote.validate_delivery(good, binding, quote, proof), good)
        for field, value in [('validated', False), ('fulfillment_confirmed', False),
                             ('trade_no', 'another-order'), ('confirmation_binding', {}), ('content', {})]:
            bad = copy.deepcopy(good)
            bad['data'][field] = value
            with self.subTest(field=field), self.assertRaises(remote.RemoteError) as error:
                remote.validate_delivery(bad, binding, quote, proof)
            self.assertEqual(error.exception.code, 'INVALID_PAID_RESULT_NO_REPAYMENT')

    def test_copy_is_independent_and_build_is_reproducible(self):
        with tempfile.TemporaryDirectory() as temp:
            relocated = Path(temp) / 'standalone'
            manifest = json.loads((ROOT / 'client-manifest.json').read_text(encoding='utf-8'))
            for name in list(manifest['members']) + ['client-manifest.json']:
                target = relocated / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            self.assertEqual(verify(relocated)['status'], 'passed')
            a, b = build(Path(temp) / 'a', relocated), build(Path(temp) / 'b', relocated)
            self.assertEqual(a['sha256'], b['sha256'])
            with zipfile.ZipFile(Path(temp) / 'a' / a['filename']) as archive:
                self.assertTrue(all(name.startswith('ziyou-mhxy-assistant-paid/') for name in archive.namelist()))
                self.assertFalse(any('/tests/' in name or '/tools/' in name for name in archive.namelist()))
            marker = Path(temp) / 'exists'
            marker.mkdir()
            (marker / 'keep').write_text('keep')
            with self.assertRaises(ValueError):
                build(marker, relocated)
            self.assertEqual((marker / 'keep').read_text(), 'keep')

    def test_extra_private_file_and_modified_runtime_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'client'
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('.git', '__pycache__', 'dist'))
            secret = root / 'secret.key'
            secret.write_text('test')
            with self.assertRaisesRegex(ValueError, 'Unlisted'):
                verify(root)
            secret.unlink()
            script = root / 'skills/ziyou-mhxy-assistant-paid/scripts/remote_client.py'
            script.write_bytes(script.read_bytes() + b'\n# modified\n')
            with self.assertRaisesRegex(ValueError, 'Hash mismatch'):
                verify(root)


if __name__ == '__main__':
    unittest.main()
