"""Distributable standard-library remote bridge. No paid algorithms or payment execution.

Natural-language interpretation belongs to the host. User files contain inputs,
provenance and revision IDs, never Payment-Proof or confirmation envelopes.
"""
import base64
from datetime import date, datetime, timezone, timedelta
import binascii
import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import hashlib
import http.client
import ssl
import socket
from urllib.parse import urlsplit

MAX_BODY = 65536
ASSET_MAX_BODY = 1_000_000
ASSET_MAX_RESPONSE = 4_000_000
SERVICE = 'ziyou-mhxy-assistant/explicit-scenario-planning-v1'
ALLOCATION_SERVICE = 'ziyou-mhxy-assistant/owned-asset-allocation-v1'
COMBINATION_SERVICE = 'ziyou-mhxy-assistant/role-combination-planning-v1'
ASSET_SERVICES = {ALLOCATION_SERVICE: 'ordinary', COMBINATION_SERVICE: 'combo'}
ASSET_GOODS = {
    ALLOCATION_SERVICE:'自游·梦幻助手：一次已有资产跨角色分配（沙箱演示）',
    COMBINATION_SERVICE:'自游·梦幻助手：一次角色套装／特技标记组合分配（沙箱演示）',
}
ASSET_PREPARE = '/v1/asset-prepare'
ASSET_CONFIRM = '/v1/asset-confirmed-calculate'
ASSET_STATE_SCHEMA = 'ziyou-asset-quote-state/v1'
MAX_PROOF = 8192
def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def fmt(value): return canonical(value)

def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('重复字段')
            result[key] = value
        return result
    def reject(_): raise ValueError('金额必须使用精确字符串')
    try: return json.loads(raw, object_pairs_hook=pairs, parse_float=reject, parse_constant=reject)
    except (UnicodeError, RecursionError) as error: raise ValueError('无效JSON') from error

class RemoteError(ValueError):
    def __init__(self, code, status=None):
        self.code, self.status = code, status
        super().__init__(code)


def trusted_profile(value):
    """Explicit operator metadata; never adopted from a remote bill or input."""
    expected = {SERVICE,*ASSET_SERVICES}
    if (not isinstance(value,dict) or set(value) != {'schema','api_base','app_id','seller_id','services'}
            or value['schema'] != 'ziyou-paid-client-production/v1'
            or value['api_base'] != 'https://47.93.82.224'
            or type(value['app_id']) is not str or not re.fullmatch(r'202\d{13}',value['app_id'])
            or type(value['seller_id']) is not str or not re.fullmatch(r'2088\d{12}',value['seller_id'])
            or not isinstance(value['services'],dict) or set(value['services']) != expected):
        raise ValueError('无效的可信正式服务配置')
    ids=set()
    for row in value['services'].values():
        if (not isinstance(row,dict) or set(row) != {'service_id','amount','currency'}
                or type(row['service_id']) is not str or not re.fullmatch(r'API_[A-F0-9]{16}',row['service_id'])
                or row['service_id'] in ids or row['amount'] != '1.00' or row['currency'] != 'CNY'):
            raise ValueError('无效的可信正式服务配置')
        ids.add(row['service_id'])
    return parse(canonical(value))


def client_from_args(args):
    profile = read_json_file(args.payment_profile) if getattr(args,'payment_profile',None) else None
    if profile is None and args.api_base == 'https://47.93.82.224':
        profile = read_json_file(ROOT / 'references/production-profile.json')
    authorization = None
    if getattr(args,'auth_stdin',False):
        # A separate first line comes from a host's secret channel. It never
        # enters the workspace, argv, result or subsequent business payload.
        packet = parse(sys.stdin.buffer.readline(1025))
        if not isinstance(packet,dict) or set(packet) != {'authorization'}:
            raise ValueError('需要独立的保密认证输入')
        authorization = packet['authorization']
    if args.api_base:
        return RemoteClient(args.api_base,allow_localhost=args.allow_localhost,timeout=args.timeout,
            profile=profile,authorization=authorization)
    if profile is not None or authorization is not None: raise ValueError('需要明确的服务地址')
    return None

class RemoteClient:
    """Explicit trusted operator configuration only. Never reads URL from input.

    No redirects, proxies, ambient credentials, cookies, payment SDK or retries.
    A failed quote may already exist: retry the SAME envelope, never buy again.
    """
    def __init__(self, api_base, *, allow_localhost=False, timeout=5, profile=None, authorization=None):
        if not isinstance(api_base, str) or any(ord(c) < 33 for c in api_base):
            raise ValueError('需要明确可信API地址')
        url = urlsplit(api_base)
        if url.username is not None or url.password is not None or '?' in api_base or '#' in api_base or url.path not in ('', '/'):
            raise ValueError('API地址只允许明确的源，不接受凭据、路径或查询')
        if not url.hostname or '%' in url.netloc or '\\' in api_base:
            raise ValueError('无效API地址')
        local = url.hostname in ('127.0.0.1', 'localhost', '::1')
        if url.scheme != 'https' and not (url.scheme == 'http' and local and allow_localhost):
            raise ValueError('生产API必须使用HTTPS；本地模拟需明确开启')
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 60:
            raise ValueError('超时必须为0至60秒')
        self.api_base = api_base
        self.scheme, self.host, self.port = url.scheme, url.hostname, url.port
        self.timeout = timeout
        self.endpoint_sha256 = digest(url.scheme + '://' + url.netloc.lower().rstrip('/') )
        self.profile = trusted_profile(profile) if profile is not None else None
        if self.profile is not None and api_base != self.profile['api_base']:
            raise ValueError('正式服务需要一致的可信源')
        if authorization is not None and (self.profile is None or url.scheme != 'https'
                or type(authorization) is not str or not re.fullmatch(r'Bearer [A-Za-z0-9_-]{43}',authorization)):
            raise ValueError('无效的独立认证输入')
        self._authorization = authorization

    def post(self, path, payload, *, proof=None):
        if path not in ('/v1/scenario-prepare', '/v1/scenario-confirmed-calculate', ASSET_PREPARE, ASSET_CONFIRM):
            raise ValueError('不支持此接口')
        headers = {'Content-Type':'application/json', 'Accept':'application/json'}
        if self._authorization is not None: headers['Authorization'] = self._authorization
        if proof is not None:
            if path not in ('/v1/scenario-confirmed-calculate', ASSET_CONFIRM):
                raise ValueError('免费准备不接受付款证明')
            payment_trade(proof)
            headers['Payment-Proof'] = proof
        body = canonical(payload).encode()
        asset_route = path in (ASSET_PREPARE, ASSET_CONFIRM)
        body_limit = ASSET_MAX_BODY if asset_route else MAX_BODY
        response_limit = ASSET_MAX_RESPONSE if asset_route else 1_000_000
        if len(body) > body_limit: raise ValueError('准备请求超出当前接口限制，请明确缩小范围；不自动删事实')
        cls = http.client.HTTPSConnection if self.scheme == 'https' else http.client.HTTPConnection
        connection = cls(self.host, self.port, timeout=self.timeout)
        try:
            connection.request('POST', path, body, headers)
            response = connection.getresponse()
            if 300 <= response.status < 400: raise RemoteError('REDIRECT_REFUSED', response.status)
            if response.getheader('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
                raise RemoteError('NON_JSON_RESPONSE', response.status)
            raw = response.read(response_limit + 1)
            if len(raw) > response_limit: raise RemoteError('RESPONSE_TOO_LARGE', response.status)
            try: data = parse(raw)
            except (ValueError, TypeError): raise RemoteError('INVALID_JSON_RESPONSE', response.status)
            if not isinstance(data, dict): raise RemoteError('INVALID_JSON_RESPONSE', response.status)
            if response.status not in (200, 402):
                # Only bounded machine codes; never echo arbitrary server text.
                code = data.get('code')
                if not isinstance(code, str) or not re.fullmatch('[A-Z0-9_]{1,100}',code): code = 'REMOTE_REQUEST_FAILED'
                raise RemoteError(code, response.status)
            result = {'http_status':response.status, 'data':data}
            bill = response.getheader('Payment-Needed')
            if bill is not None:
                if len(bill)>16384 or len(response.headers.get_all('Payment-Needed',[])) != 1:
                    raise RemoteError('INVALID_BILL_HEADER', response.status)
                result['payment_needed'] = bill
            receipt = response.getheader('Payment-Validation')
            if receipt is not None:
                if len(receipt)>16384 or len(response.headers.get_all('Payment-Validation',[])) != 1:
                    raise RemoteError('INVALID_PAYMENT_VALIDATION', response.status)
                result['payment_validation'] = receipt
            return result
        except (OSError, http.client.HTTPException) as error:
            raise RemoteError('TRANSPORT_UNCERTAIN_RETRY_SAME_REQUEST') from error
        finally: connection.close()



def sync_parent(filename):
    # Directory fsync makes successful file creation durable on supported POSIX.
    if os.name == 'posix':
        fd = os.open(str(Path(filename).parent), os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try: os.fsync(fd)
        finally: os.close(fd)


def remove_own_partial(filename, identity):
    try:
        info = os.lstat(filename)
        if (info.st_dev, info.st_ino) == identity: os.unlink(filename)
    except OSError: pass

SCHEMA = 'ziyou-scenario-workspace/v1'
ROOT = Path(__file__).resolve().parents[1]


def free_dossier():
    # Load only the bundled unchanged free package, never a path from user data.
    name = '_ziyou_free_scripts'
    if name not in sys.modules:
        spec = importlib.util.spec_from_loader(name, loader=None, is_package=True)
        module = importlib.util.module_from_spec(spec)
        module.__path__ = [str(ROOT / 'basic/scripts')]
        sys.modules[name] = module
    from importlib import import_module
    return import_module(name + '.dossier')


def checked(value):
    free_dossier()._bounded(value)
    def no_credentials(v):
        if isinstance(v, dict):
            for k, child in v.items():
                if k.lower().replace('-', '_') in {'payment_proof','confirmation_hash','password','api_key','access_token','private_key','authorization','order_id','bill','payment_needed','payment_validation','input_summary_hash','resource_id','token','secret','client_secret','cookie','api_base','endpoint','url'}:
                    raise ValueError('工作区不接受密码、密钥、付款证明或确认令牌')
                no_credentials(child)
        elif isinstance(v, list):
            for child in v: no_credentials(child)
    no_credentials(value)
    if len(canonical(value).encode()) > 1_000_000:
        raise ValueError('工作区过大，请拆分')
    # JSON value semantics: eliminate shared Python container aliases so a
    # precise edit cannot silently change a second scenario.
    return parse(canonical(value))


def locate(root, path):
    """Explicit object paths, stable @id array selection; no positional guessing."""
    if not isinstance(path, str) or not path.startswith('/') or len(path) > 500:
        raise ValueError('请明确要修改的字段')
    parts = path[1:].split('/')
    if any(not p or '~' in p for p in parts): raise ValueError('不支持此字段路径')
    node = root
    for part in parts[:-1]:
        if isinstance(node, list):
            rows = [x for x in node if isinstance(x, dict) and
                    (part == '@' + str(x.get('id', '')) or
                     (part.startswith('@label=') and part[7:] == x.get('label')))]
            if len(rows) != 1: raise ValueError('请明确要修改哪个项目或情况：' + part)
            node = rows[0]
        elif isinstance(node, dict) and part in node: node = node[part]
        else: raise ValueError('请明确已有字段：' + part)
    key = parts[-1]
    if not isinstance(node, dict) or key not in node: raise ValueError('请明确已有字段：' + key)
    return node, key


def validate_binding(binding):
    if (not isinstance(binding, dict) or set(binding) != {'draft_id','previous_revision','endpoint_sha256'}
            or not isinstance(binding['draft_id'], str) or not re.fullmatch('[a-f0-9]{32}', binding['draft_id'])
            or type(binding['previous_revision']) is not int or binding['previous_revision'] < 1
            or not isinstance(binding['endpoint_sha256'], str) or not re.fullmatch('[a-f0-9]{64}', binding['endpoint_sha256'])):
        raise ValueError('草稿绑定无效')


def validate_prepared(data, request, client, binding):
    service = request['service']
    try:
        new_binding = dict(draft_id=data['draft_id'], previous_revision=data['revision'], endpoint_sha256=client.endpoint_sha256)
        validate_binding(new_binding)
        if not isinstance(data['confirmation_hash'],str) or not re.fullmatch('[a-f0-9]{64}',data['confirmation_hash']): raise ValueError()
        if binding and (new_binding['draft_id'] != binding['draft_id'] or
                new_binding['previous_revision'] not in (binding['previous_revision'], binding['previous_revision'] + 1)):
            raise ValueError()
        if not binding and new_binding['previous_revision'] != 1: raise ValueError()
        summary = data['summary']
        if summary['service'] != service: raise ValueError()
        if type(data.get('expires')) is not int or data['expires'] <= 0 or data.get('charge_created') is not False: raise ValueError()
        datetime.fromtimestamp(data['expires'], timezone.utc)
        for field in ('known','assumed','unresolved','limitations'):
            if not isinstance(summary.get(field),list) or any(not isinstance(x,str) for x in summary[field]): raise ValueError()
        if not summary['known'] or not summary['limitations'] or summary['unresolved']: raise ValueError()
        price = summary['price']
        profile = getattr(client,'profile',None)
        expected_amount = profile['services'][service]['amount'] if profile is not None else '0.10'
        if not isinstance(price,dict) or price.get('amount') != expected_amount or price.get('currency') != 'CNY': raise ValueError()
        if any(not isinstance(price.get(k),str) or not price[k] for k in ('commitment','provider')): raise ValueError()
        if not isinstance(summary.get('prompt'),str) or not summary['prompt']: raise ValueError()
        if not re.fullmatch('[a-f0-9]{64}',data['summary']['input_summary_hash']): raise ValueError()
        if summary.get('assumed') != request['assumptions'] or summary.get('hypothetical') is not request['hypothetical']:
            raise ValueError()
        # Recompute both hashes from OUR input and the complete returned
        # summary. A syntactically valid hash from another input is unsafe.
        unsigned = dict(summary); unsigned.pop('input_summary_hash')
        identity_request = {'service':service, 'input':request['input']}
        if service in ASSET_SERVICES:
            identity_request.update(analysis_mode=ASSET_SERVICES[service],
                evaluation_date=summary['evaluation_date'], evaluation_timezone='Asia/Shanghai')
        request_hash = digest(canonical(identity_request))
        identity = digest(canonical({'request':request_hash, 'summary':unsigned,
            'calculator':service, 'amount':expected_amount, 'currency':'CNY'}))
        bound = digest(canonical({'id':data['draft_id'], 'revision':data['revision'],
            'expires':data['expires'], 'identity':identity}))
        if summary.get('calculator') != service or summary['input_summary_hash'] != identity or data['confirmation_hash'] != bound:
            raise ValueError()
    except (ValueError, KeyError, TypeError, OverflowError, OSError): raise RemoteError('INVALID_PREPARE_RESPONSE')
    return new_binding


def validate_quote(result, envelope, profile=None):
    profile = trusted_profile(profile) if profile is not None else None
    expected_amount = profile['services'][envelope['service']]['amount'] if profile is not None else '0.10'
    quote = result['data']
    if (result['http_status'] != 402 or quote.get('code') != 'PAYMENT_REQUIRED'
            or quote.get('amount') != expected_amount or quote.get('currency') != 'CNY'
            or not isinstance(quote.get('resource_id'),str) or not re.fullmatch('[a-f0-9]{32}',quote['resource_id'])
            or not isinstance(result.get('payment_needed'),str) or not result['payment_needed']):
        raise RemoteError('INVALID_QUOTE_RESPONSE')
    expected_binding = {k:envelope[k] for k in ('service','draft_id','revision','confirmation_hash','input_summary_hash')}
    if (quote.get('confirmation_binding') != expected_binding
            or type(quote['confirmation_binding'].get('revision')) is not int):
        raise RemoteError('INVALID_QUOTE_RESPONSE')
    try:
        bill = result['payment_needed']
        decoded = parse(base64.b64decode(bill + '=' * (-len(bill) % 4), altchars=b'-_', validate=True))
        protocol = decoded['protocol']
        if (protocol['resource_id'] != quote['resource_id'] or protocol['amount'] != expected_amount
                or protocol['currency'] != 'CNY' or not isinstance(protocol['out_trade_no'],str)
                or not re.fullmatch('[a-f0-9]{32}',protocol['out_trade_no'])):
            raise ValueError()
        if profile is not None:
            method = decoded['method']
            goods = (ASSET_GOODS[envelope['service']].removesuffix('（沙箱演示）')
                if envelope['service'] in ASSET_SERVICES else '自游·梦幻助手：一次录入多情景现金规划')
            if (method.get('service_id') != profile['services'][envelope['service']]['service_id']
                    or method.get('seller_app_id') != profile['app_id']
                    or method.get('seller_id') != profile['seller_id']
                    or method.get('seller_unique_id_key') != 'seller_id'
                    or protocol.get('seller_unique_id') != profile['seller_id']
                    or method.get('goods_name') != goods or protocol.get('seller_sign_type') != 'RSA2'
                    or not isinstance(protocol.get('seller_signature'),str)
                    or len(base64.b64decode(protocol['seller_signature'],validate=True)) < 256
                    or not isinstance(protocol.get('pay_before'),str)
                    or datetime.fromisoformat(protocol['pay_before']).tzinfo is None):
                raise ValueError()
        elif envelope['service'] in ASSET_SERVICES:
            method = decoded['method']
            if (method.get('goods_name') != ASSET_GOODS[envelope['service']]
                    or method.get('service_id') != 'api_mock_service_id'
                    or not isinstance(protocol.get('pay_before'), str)
                    or datetime.fromisoformat(protocol['pay_before']).tzinfo is None):
                raise ValueError()
    except (ValueError, TypeError, KeyError, AttributeError, binascii.Error):
        raise RemoteError('INVALID_QUOTE_RESPONSE')
    return result


def confirmation_text(prepared):
    """Render the entire verified summary and bound expiry for host display."""
    summary = prepared['summary']
    expires = datetime.fromtimestamp(prepared['expires'], timezone(timedelta(hours=8))).isoformat()
    lines = ['服务：' + summary['service'], '当前修订：' + str(prepared['revision']),
             '摘要有效期至：' + expires + '（Asia/Shanghai；到期停止确认，不自动续期）']
    for field, label in [('known','已知事实'),('assumed','假设'),('unresolved','未决项'),('limitations','限制')]:
        lines.append(label + '：')
        lines.extend('- ' + item for item in summary[field])
        if not summary[field]: lines.append('- 无')
    # Extra bound fields (mode, source revision/date, impossibility notices)
    # must not disappear when the host uses the ready-to-display text.
    for key, value in summary.items():
        if key not in ('service','known','assumed','unresolved','limitations','price','prompt','input_summary_hash'):
            lines.append(key + '：' + fmt(value))
    price = summary['price']
    lines.extend(['单次服务费：' + price['amount'] + ' ' + price['currency'],
                  '费用范围：' + price['commitment'], '支付说明：' + price['provider'], summary['prompt']])
    return '\n'.join(lines)


def official_payment_request(result, client, path, payload):
    """Carry the exact original POST for the official buyer's resource retry.

    Only production request-scoped checkout needs this handoff. No bearer
    credentials or payment proof are copied into tool output or player files.
    """
    if getattr(client, 'profile', None) is not None and getattr(client, '_authorization', None) is None:
        result['payment_request'] = dict(resource_url=client.api_base + path,
            method='POST', data=canonical(payload), headers={'Content-Type':'application/json','Accept':'application/json'})
    return result


def payment_trade(proof):
    """Validate bounded opaque header shape only; the server verifies payment."""
    try:
        if (not isinstance(proof, str) or not 1 <= len(proof) <= MAX_PROOF
                or not re.fullmatch(r'[A-Za-z0-9_+/=-]+', proof)):
            raise ValueError()
        value = parse(base64.b64decode(proof + '=' * (-len(proof) % 4), altchars=b'-_', validate=True))
        protocol, method = value['protocol'], value.get('method', {})
        if not isinstance(protocol, dict) or not isinstance(method, dict): raise ValueError()
        for key, cap in [('payment_proof',256),('trade_no',64)]:
            if not isinstance(protocol.get(key), str) or not 1 <= len(protocol[key]) <= cap: raise ValueError()
        session = method.get('client_session')
        if session is not None and (not isinstance(session, str) or len(session)>1024): raise ValueError()
        return protocol['trade_no']
    except (ValueError, TypeError, KeyError, AttributeError, binascii.Error):
        raise RemoteError('INVALID_PAYMENT_PROOF') from None


def validate_delivery(result, envelope, quote, proof, profile=None):
    """Release only a fulfilled response bound to the original bill and input."""
    validate_quote(quote, envelope, profile)
    try:
        bill = parse(base64.b64decode(quote['payment_needed'] + '=' * (-len(quote['payment_needed']) % 4), altchars=b'-_', validate=True))
        expected = dict(validated=True, trade_no=payment_trade(proof),
                        out_trade_no=bill['protocol']['out_trade_no'], resource_id=quote['data']['resource_id'])
        data = result['data']
        if result['http_status'] != 200: raise ValueError()
        header = result.get('payment_validation')
        if not isinstance(header, str) or not header or len(header)>16384: raise ValueError()
        receipt = parse(base64.b64decode(header + '=' * (-len(header) % 4), altchars=b'-_', validate=True))
        if receipt != expected or receipt.get('validated') is not True: raise ValueError()
        if any(data.get(k) != v for k,v in expected.items()) or data.get('validated') is not True: raise ValueError()
        binding = {k:envelope[k] for k in ('service','draft_id','revision','confirmation_hash','input_summary_hash')}
        if (data.get('confirmation_binding') != binding
                or type(data['confirmation_binding'].get('revision')) is not int
                or data.get('fulfillment_confirmed') is not True
                or not isinstance(data.get('content'),dict) or not data['content'] or 'payment_needed' in result):
            raise ValueError()
        if envelope['service'] in ASSET_SERVICES:
            content = data['content']
            if (content.get('service') != envelope['service']
                    or content.get('analysis_mode') != ASSET_SERVICES[envelope['service']]
                    or content.get('evaluation_timezone') != 'Asia/Shanghai'):
                raise ValueError()
    except (ValueError, TypeError, KeyError, AttributeError, binascii.Error):
        raise RemoteError('INVALID_PAID_RESULT_NO_REPAYMENT') from None
    return result


def retrieval_input(value):
    if not isinstance(value, dict) or set(value) != {'confirmation','quote','payment_proof'}:
        raise ValueError('取回结果需要原信封、原账单和官方返回的证明；不从资料文件取证明')
    payment_trade(value['payment_proof'])
    return value['confirmation'], value['quote'], value['payment_proof']



class Workspace:
    def __init__(self, data):
        data = checked(data)
        if set(data) != {'schema','revision','request','origin','history','binding'} or data['schema'] != SCHEMA:
            raise ValueError('工作区格式不支持')
        if type(data['revision']) is not int or data['revision'] < 1: raise ValueError('版本无效')
        req = data['request']
        if not isinstance(req, dict) or set(req) != {'service','input','unresolved','assumptions','goal_supported','hypothetical'} or req['service'] != SERVICE:
            raise ValueError('服务或输入字段不支持')
        if not isinstance(req['input'], dict): raise ValueError('输入必须是对象')
        base = req['input'].get('base', {})
        if not isinstance(base, dict) or not isinstance(base.get('context', {}), dict):
            raise ValueError('基础输入和区服信息必须是对象')
        if not isinstance(data['origin'], dict) or not isinstance(data['history'], list): raise ValueError('来源记录无效')
        b = data['binding']
        if b is not None and (not isinstance(b, dict) or set(b) != {'draft_id','previous_revision','endpoint_sha256'} or not isinstance(b.get('endpoint_sha256'),str) or not re.fullmatch('[a-f0-9]{64}',b['endpoint_sha256']) or not isinstance(b['draft_id'],str) or not re.fullmatch('[a-f0-9]{32}',b['draft_id']) or type(b['previous_revision']) is not int or b['previous_revision'] < 1):
            raise ValueError('草稿绑定无效')
        self.data = data
        self._needs_reference_date = False

    @classmethod
    def create(cls, request, *, source):
        if not isinstance(source,str) or not source.strip(): raise ValueError('需要输入来源')
        return cls(dict(schema=SCHEMA, revision=1, request=request,
                        origin={'source':source}, history=[], binding=None))

    @classmethod
    def from_dossier(cls, value, step_id, scenarios, *, assumptions, hypothetical):
        d = free_dossier()
        compiled = d.compile_dossier(value)  # Saved computations never trusted.
        rows = [s for s in compiled['compilation']['steps'] if s['id'] == step_id and s['kind'] == 'portfolio']
        if len(rows) != 1: raise ValueError('请指定档案中的免费联合规划步骤')
        row = rows[0]
        if row['status'] == 'blocked' or row['resolved_input'] is None:
            raise ValueError('档案仍有未知或阻塞事实，请先免费补充：' + fmt(row['blockers']))
        conditions = [fmt(c) for c in row['conditions']]
        req = dict(service=SERVICE,input=dict(schema_version=1,base=row['resolved_input'],scenarios=scenarios),
                   unresolved=[],assumptions=list(assumptions)+conditions,goal_supported=True,hypothetical=hypothetical)
        result = cls.create(req,source='复用免费档案 '+compiled['dossier']['id']+' / '+step_id)
        result.data['origin'].update(dossier=compiled['dossier'], step_id=step_id,
            source_sha256=compiled['compilation']['input_sha256'], conditions=row['conditions'], price_conditions=row['price_conditions'])
        result = cls(result.data)
        result._needs_reference_date = True
        return result

    def _invalidate(self, client):
        binding = self.data['binding']
        if binding:
            self._check_endpoint(client)
            request = dict(service=SERVICE, input={}, unresolved=['用户取消或修改，停止旧确认和旧账单付款'],
                           assumptions=[], goal_supported=True, hypothetical=False)
            request.update({k:binding[k] for k in ('draft_id','previous_revision')})
            response = client.post('/v1/scenario-prepare', request)
            if (response['http_status'] != 200 or response['data'].get('status') != 'needs_clarification'
                    or response['data'].get('revoked_binding') != {'draft_id':binding['draft_id'], 'revision':binding['previous_revision']}):
                raise RemoteError('REVOCATION_NOT_VERIFIED')

    def _check_endpoint(self, client):
        if not isinstance(client, RemoteClient): raise ValueError('需要明确配置的原API服务')
        binding = self.data['binding']
        if binding and binding['endpoint_sha256'] != client.endpoint_sha256:
            raise ValueError('原草稿属于另一API；不能把保存文件中的地址作为配置')

    def cancel(self, client):
        self._invalidate(client)
        return {'status':'cancelled', 'charge_created':False,
                'notice':'旧确认已停用；支付方旧账单不保证撤销，停止付款。已付订单走原官方恢复，不重复买。'}

    def edit(self, changes, *, source, client=None):
        """Atomic explicit set with compare-and-set. Invalid edits revoke old quote.

        A change has path, before and after; replacing a compound field is explicit.
        Unmentioned source dates/status/unknowns remain byte-for-byte unchanged.
        """
        self._invalidate(client)
        new = checked(self.data)
        if not isinstance(source,str) or not source.strip() or len(source)>500: raise ValueError('需要本次纠正来源')
        if not isinstance(changes,list) or not 1 <= len(changes) <= 32: raise ValueError('请明确一项或多项更改')
        paths = []
        for c in changes:
            if not isinstance(c,dict) or set(c) != {'path','before','after'}: raise ValueError('更改需包含明确字段与前后值')
            p = c['path']
            if not isinstance(p,str) or any(p == x or p.startswith(x+'/') or x.startswith(p+'/') for x in paths): raise ValueError('重复或重叠更改')
            if p == '/service': raise ValueError('不能修改服务标识')
            node,key = locate(new['request'],p)
            if canonical(node[key]) != canonical(c['before']): raise ValueError('旧值不一致，请核对最新数据：'+p)
            node[key] = copy.deepcopy(c['after']); paths.append(p)
        new['revision'] += 1
        new['history'].append(dict(source=source,changes=copy.deepcopy(changes),parent_sha256=digest(canonical(self.data['request']))))
        validated = Workspace(new)
        self.data = validated.data
        return {'status':'edited_requires_preparation','charge_created':False,
                'changes':[c['path']+'：'+fmt(c['before'])+' → '+fmt(c['after']) for c in changes],
                'notice':'只更新列出的字段；报价日期、来源和未知状态未自动刷新。原账单不得继续支付，原已付订单仅用原信封与证明恢复。'}

    def prepare(self, client, *, reference_date=None):
        self._check_endpoint(client)
        saved_date = self.data['request'].get('input', {}).get('base', {}).get('context', {}).get('as_of')
        if self._needs_reference_date and reference_date is None or reference_date is not None and reference_date != saved_date:
            self._invalidate(client)
            return {'status':'needs_clarification','questions':['请明确仍按原核价日 '+str(saved_date)+' 计算，或先修改日期并重新核验报价'], 'charge_created':False}
        request = checked(self.data['request'])
        binding = self.data['binding']
        if binding: request.update({k:binding[k] for k in ('draft_id','previous_revision')})
        if len(canonical(request).encode()) > MAX_BODY:
            self._invalidate(client)
            raise ValueError('准备请求超过64KiB，请拆分')
        response = client.post('/v1/scenario-prepare', request)
        data = response['data']
        if response['http_status'] != 200: raise RemoteError('UNEXPECTED_PREPARE_STATUS')
        if data.get('status') == 'prepared':
            new_binding = validate_prepared(data, request, client, binding)
            self.data['binding'] = new_binding
            data['request_sha256'] = digest(canonical(self.data['request']))
            data['confirmation_text'] = confirmation_text(data)
            self._needs_reference_date = False
        elif data.get('status') != 'needs_clarification': raise RemoteError('INVALID_PREPARE_RESPONSE')
        return data

    def confirm(self, client, envelope, *, consent=False):
        if consent is not True: raise ValueError('必须先由当前用户明确确认全量摘要、服务及价格；不等于付款授权')
        payload = self._confirmation_payload(client, envelope)
        result=validate_quote(client.post('/v1/scenario-confirmed-calculate', payload), envelope, getattr(client,'profile',None))
        return official_payment_request(result,client,'/v1/scenario-confirmed-calculate',payload)

    def _confirmation_payload(self, client, envelope):
        self._check_endpoint(client)
        binding = self.data['binding']
        expected = {'service','draft_id','revision','confirmation_hash','input_summary_hash','decision','request_sha256'}
        if not isinstance(envelope,dict) or set(envelope) != expected: raise ValueError('需要当前完整确认信封及输入指纹')
        if not binding or envelope['service'] != SERVICE or envelope['draft_id'] != binding['draft_id'] or envelope['revision'] != binding['previous_revision'] or envelope['request_sha256'] != digest(canonical(self.data['request'])):
            raise ValueError('输入或修订已改变，需重新免费准备并确认')
        if envelope['decision'] != 'confirm_summary_service_and_price': raise ValueError('需要明确确认决定')
        payload = {k:v for k,v in envelope.items() if k != 'request_sha256'}
        payload['input'] = copy.deepcopy(self.data['request']['input'])
        return payload

    def retrieve(self, client, envelope, quote, proof):
        payload = self._confirmation_payload(client, envelope)
        payment_trade(proof)
        validate_quote(quote, envelope, getattr(client,'profile',None))
        result = client.post('/v1/scenario-confirmed-calculate', payload, proof=proof)
        return validate_delivery(result, envelope, quote, proof, getattr(client,'profile',None))

    def save(self, filename):
        """Explicit new user file only, private mode; never overwrite/follow symlinks."""
        content = canonical(Workspace(self.data).data).encode()
        fd = os.open(filename, os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        info = os.fstat(fd); identity = (info.st_dev, info.st_ino)
        try:
            with os.fdopen(fd,'wb') as f:
                f.write(content); f.flush(); os.fsync(f.fileno())
            sync_parent(filename)
        except BaseException:
            remove_own_partial(filename, identity)
            raise

    @classmethod
    def open(cls, filename):
        fd=os.open(filename,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(fd,'rb') as f:
            info=os.fstat(f.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size>1_000_000: raise ValueError('需要不超过1MB的普通工作区文件')
            raw=f.read(1_000_001)
        if len(raw)>1_000_000: raise ValueError('工作区过大')
        def pairs(xs):
            out={}
            for k,v in xs:
                if k in out: raise ValueError('重复字段')
                out[k]=v
            return out
        def reject(_): raise ValueError('金额用精确字符串，禁止浮点数')
        result = cls(json.loads(raw,object_pairs_hook=pairs,parse_float=reject,parse_constant=reject))
        result._needs_reference_date = True
        return result

def read_json_file(filename):
    """Bounded regular-file read, preserving precise JSON and rejecting symlinks."""
    fd = os.open(filename, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 1_000_000:
            raise ValueError('需要不超过1MB的普通JSON文件')
        raw = stream.read(1_000_001)
    if len(raw) > 1_000_000: raise ValueError('输入超过1MB')
    return parse(raw)


def neutral_asset_document(value):
    """Transport shape only; free server preflight owns factual/strict checks.

    No solver or private intake editor is imported into the distributable client.
    The complete neutral document, including provenance/history, remains primary.
    """
    value = checked(value)
    required = {'schema','revision','request','ambiguities','source','history'}
    if (not isinstance(value, dict) or not required <= set(value)
            or set(value) - required - {'combination'}
            or value['schema'] not in ('ziyou-asset-intake/v1', 'ziyou-asset-intake/v2')
            or (value['schema'] == 'ziyou-asset-intake/v1' and 'combination' in value)
            or type(value['revision']) is not int or not 1 <= value['revision'] <= 100
            or not isinstance(value['request'], dict) or not isinstance(value['ambiguities'], list)
            or not isinstance(value['source'], str) or not value['source'].strip()
            or not isinstance(value['history'], list)):
        raise ValueError('需要完整的中立资产资料文件；部分事实可以保持未知')
    return value


class AssetSession:
    """Non-editable quote metadata, never a second facts archive or proof store.

    The host supplies an explicitly selected service and the authoritative neutral
    document on every call. A trusted localhost host attests consent; this code
    cannot authenticate the human or grant payment authority.
    """
    def __init__(self, state):
        state = checked(state)
        if (not isinstance(state, dict) or set(state) != {
                'schema','service','input_sha256','request_sha256','binding'}
                or state['schema'] != ASSET_STATE_SCHEMA or state['service'] not in ASSET_SERVICES):
            raise ValueError('收费准备状态格式或服务不支持')
        for key in ('input_sha256','request_sha256'):
            if state[key] is not None and (not isinstance(state[key], str) or not re.fullmatch('[a-f0-9]{64}', state[key])):
                raise ValueError('输入指纹无效')
        if (state['input_sha256'] is None) != (state['request_sha256'] is None):
            raise ValueError('输入指纹不完整')
        if state['binding'] is not None:
            validate_binding(state['binding'])
            if state['request_sha256'] is None: raise ValueError('绑定缺少输入指纹')
        self.data = state

    @classmethod
    def create(cls, service):
        return cls(dict(schema=ASSET_STATE_SCHEMA, service=service,
                        input_sha256=None, request_sha256=None, binding=None))

    @classmethod
    def open(cls, filename):
        return cls(read_json_file(filename))

    def _check_endpoint(self, client):
        if not isinstance(client, RemoteClient): raise ValueError('需要明确配置的原API服务')
        binding = self.data['binding']
        if binding and binding['endpoint_sha256'] != client.endpoint_sha256:
            raise ValueError('原收费准备属于另一API；请使用原可信服务配置')

    def _invalidate(self, client):
        self._check_endpoint(client)
        binding = self.data['binding']
        if binding is None: return
        payload = dict(service=self.data['service'], input={},
                       unresolved=['用户取消或修改，停止旧确认和旧账单付款'],
                       assumptions=[], goal_supported=True, hypothetical=False,
                       draft_id=binding['draft_id'], previous_revision=binding['previous_revision'])
        response = client.post(ASSET_PREPARE, payload)
        data = response['data']
        if (response['http_status'] != 200 or data.get('status') != 'needs_clarification'
                or data.get('charge_created') is not False
                or data.get('revoked_binding') != {'draft_id':binding['draft_id'], 'revision':binding['previous_revision']}):
            raise RemoteError('REVOCATION_NOT_VERIFIED')

    def cancel(self, client):
        self._invalidate(client)
        return {'status':'cancelled', 'charge_created':False,
                'notice':'旧确认已停用；支付方旧账单不保证撤销，停止付款。已付订单走原官方恢复，不重复买。'}

    def prepare(self, client, document, flags):
        self._check_endpoint(client)
        binding = self.data['binding']
        try:
            document = neutral_asset_document(document)
            flags = checked(flags)
            if (not isinstance(flags, dict) or set(flags) != {'unresolved','assumptions','goal_supported','hypothetical'}
                    or type(flags['goal_supported']) is not bool or type(flags['hypothetical']) is not bool):
                raise ValueError('需要明确的当前澄清、假设与目标标记')
            for key in ('unresolved','assumptions'):
                if (not isinstance(flags[key], list) or len(flags[key]) > 100
                        or any(not isinstance(x, str) or not x.strip() or len(x) > 2000 for x in flags[key])):
                    raise ValueError('需要有界、明确的澄清和假设列表')
            request = dict(service=self.data['service'], input=document, **flags)
            request_sha256 = digest(canonical(request))
            if binding: request.update({k:binding[k] for k in ('draft_id','previous_revision')})
            if len(canonical(request).encode()) > ASSET_MAX_BODY: raise ValueError('资产请求超过1MB，请明确缩小范围；不自动删事实')
        except (ValueError, TypeError, KeyError):
            self._invalidate(client)
            raise
        response = client.post(ASSET_PREPARE, request)
        data = response['data']
        if response['http_status'] != 200: raise RemoteError('UNEXPECTED_PREPARE_STATUS')
        next_binding = binding
        if data.get('status') == 'prepared':
            next_binding = validate_prepared(data, request, client, binding)
            summary = data['summary']
            if (summary.get('analysis_mode') != ASSET_SERVICES[self.data['service']]
                    or summary.get('source_revision') != document['revision']
                    or not isinstance(summary.get('evaluation_date'), str)
                    or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', summary['evaluation_date'])
                    or summary.get('evaluation_timezone') != 'Asia/Shanghai'
                    or summary.get('source_content_sha256') != digest(canonical({
                        k:document[k] for k in ('request','ambiguities','combination') if k in document}))):
                raise RemoteError('INVALID_PREPARE_RESPONSE')
            try: date.fromisoformat(summary['evaluation_date'])
            except ValueError: raise RemoteError('INVALID_PREPARE_RESPONSE')
            data['request_sha256'] = request_sha256
            data['confirmation_text'] = confirmation_text(data)
        elif data.get('status') == 'needs_clarification':
            if (data.get('charge_created') is not False
                    or not isinstance(data.get('questions'), list) or not 1 <= len(data['questions']) <= 2
                    or any(not isinstance(x, str) or not x for x in data['questions'])
                    or not isinstance(data.get('unresolved'), list) or not data['unresolved']
                    or any(not isinstance(x, str) or not x for x in data['unresolved'])
                    or (binding and data.get('revoked_binding') != {
                        'draft_id':binding['draft_id'], 'revision':binding['previous_revision']})):
                raise RemoteError('INVALID_PREPARE_RESPONSE')
        else: raise RemoteError('INVALID_PREPARE_RESPONSE')
        candidate = dict(self.data, input_sha256=digest(canonical(document)),
                         request_sha256=request_sha256, binding=next_binding)
        self.data = AssetSession(candidate).data
        return data

    def confirm(self, client, document, envelope, *, consent=False):
        if consent is not True:
            raise ValueError('必须先由当前用户明确确认全量摘要、服务及价格；不等于付款授权')
        payload = self._confirmation_payload(client, document, envelope)
        result=validate_quote(client.post(ASSET_CONFIRM, payload), envelope, getattr(client,'profile',None))
        return official_payment_request(result,client,ASSET_CONFIRM,payload)

    def _confirmation_payload(self, client, document, envelope, *, revoke_changed=True):
        self._check_endpoint(client)
        try: document = neutral_asset_document(document)
        except (ValueError, TypeError, KeyError):
            if revoke_changed: self._invalidate(client)
            raise
        if digest(canonical(document)) != self.data['input_sha256']:
            if revoke_changed: self._invalidate(client)
            raise ValueError('资料已改变，旧确认不可用于新资料；原已付结果只用原资料恢复')
        expected = {'service','draft_id','revision','confirmation_hash','input_summary_hash','decision','request_sha256'}
        binding = self.data['binding']
        if (not isinstance(envelope, dict) or set(envelope) != expected or not binding
                or envelope['service'] != self.data['service']
                or envelope['draft_id'] != binding['draft_id'] or envelope['revision'] != binding['previous_revision']
                or envelope['request_sha256'] != self.data['request_sha256']
                or envelope['decision'] != 'confirm_summary_service_and_price'):
            raise ValueError('需要同一服务、输入和修订的完整确认信封；不能沿用旧确认')
        for key in ('confirmation_hash','input_summary_hash'):
            if not isinstance(envelope[key], str) or not re.fullmatch('[a-f0-9]{64}', envelope[key]):
                raise ValueError('确认信封无效')
        payload = {k:v for k,v in envelope.items() if k != 'request_sha256'}
        payload['input'] = document
        return payload

    def retrieve(self, client, document, envelope, quote, proof):
        payload = self._confirmation_payload(client, document, envelope, revoke_changed=False)
        payment_trade(proof)
        validate_quote(quote, envelope, getattr(client,'profile',None))
        result = client.post(ASSET_CONFIRM, payload, proof=proof)
        result = validate_delivery(result, envelope, quote, proof, getattr(client,'profile',None))
        content = result['data']['content']
        if (content.get('source_revision') != document['revision']
                or content.get('input_sha256') != free_asset_draft().digest(document)
                or content.get('evaluation_date') != document['request']['input']['context']['as_of']):
            raise RemoteError('INVALID_PAID_RESULT_NO_REPAYMENT')
        return result

    def save(self, filename):
        save_new_json(filename, AssetSession(self.data).data)


def save_new_json(filename, value):
    content = canonical(value).encode()
    fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    info = os.fstat(fd); identity = (info.st_dev, info.st_ino)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content); stream.flush(); os.fsync(stream.fileno())
        sync_parent(filename)
    except BaseException:
        remove_own_partial(filename, identity)
        raise


ASSET_LOCAL_COMMANDS = ('asset-create','asset-load','asset-save','asset-edit','asset-inspect')


def free_asset_draft():
    """Fixed sibling data-only editor; no path from player input and no solver."""
    name = '_ziyou_public_asset_draft'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT/'scripts/asset_draft.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try: spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    return sys.modules[name]


def asset_local_main(args):
    """Free public facts workflow. Confirm/payment metadata never enters files."""
    reserved=None;identity=None;completed=False;stage='configure'
    try:
        action=args.command.removeprefix('asset-')
        if args.service is not None or args.consent or args.reference_date is not None:
            raise ValueError('免费资料操作不接受服务费确认或历史分析参数')
        if args.state and action!='edit': raise ValueError('仅修改可引用原报价状态撤销确认')
        if args.mode is not None and action not in ('load','inspect'):
            raise ValueError('只有免费查看／检查可以指定检查模式')
        stage='revoke'
        # Revoke BEFORE parsing facts, edits or output paths. An unconfirmed
        # revocation blocks this edit; the original authoritative file is intact.
        prior=None
        if args.state:
            prior=AssetSession.open(args.state)
            client=client_from_args(args)
            prior._invalidate(client)
        stage='load'
        if (action=='create') == bool(args.workspace): raise ValueError('创建不读取旧文件；其他操作需要明确资料文件')
        writes=action in ('create','save','edit')
        if bool(args.output) != writes: raise ValueError('写入需要明确新文件名；只读操作不写文件')
        module=free_asset_draft()
        data=module.checked(checked(read_json_file(args.workspace))) if args.workspace else None
        if prior and prior.data['input_sha256'] not in (None,digest(canonical(data))):
            raise ValueError('原报价状态不匹配当前资料；已停用所引用确认，请核对要修改的原资料')
        stage='reserve'
        if writes:
            reserved=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
            info=os.fstat(reserved);identity=(info.st_dev,info.st_ino)
        stage='parse'
        if action in ('create','edit'):
            raw=sys.stdin.buffer.read(1_000_001)
            if len(raw)>1_000_000:raise ValueError('输入超过1MB')
            payload=checked(parse(raw))
            if not isinstance(payload,dict):raise ValueError('宿主输入必须是对象')
            if action=='create':
                if not {'request','source'}<=set(payload) or set(payload)-{'request','source','ambiguities','combination'}:
                    raise ValueError('创建字段不支持')
                data=module.create(**payload)
            else:
                if set(payload)!={'expected_revision','expected_content_sha256','operations','source'}:
                    raise ValueError('修改需要原修订、内容哈希、精确操作和来源')
                data=module.edit(data,**payload)
        stage='action'
        report=module.inspect(data,args.mode)
        report.update(charge_created=False,analysis_returned=False,notice='资料保存、补答、检查与修改免费；没有计算、账单或付款动作。')
        if action!='inspect':
            report.update(action_status='saved' if writes else 'loaded',draft=data)
        if action=='edit':
            report['changes']=data['history'][-1]['changes']
            report['requires_new_paid_confirmation']=True
            report['quote_notice']='只修改资料；如继续新增收费分析，须重新免费准备并展示全量摘要。旧账单停止付款。'
            if prior:
                report['quote_continuation'] = dict(command='asset-prepare', workspace=args.output,
                    state=args.state, service=prior.data['service'], requires_new_output=True,
                    notice='接续准备必须携带此原状态；保留草稿ID，不能省略state另建草稿。修改不等于同意收费。')
        stage='export'
        if reserved is not None:
            with os.fdopen(reserved,'wb') as stream:
                reserved=None;stream.write(canonical(data).encode());stream.flush();os.fsync(stream.fileno())
            sync_parent(args.output);completed=True
        print(canonical(report));return 0
    except (ValueError,OSError,TypeError,KeyError,AttributeError,RecursionError,OverflowError) as error:
        report={'status':'blocked','code':error.code if isinstance(error,RemoteError) else 'INVALID_LOCAL_REQUEST',
                'charge_created':False,'analysis_returned':False,
                'notice':'未确认完成；原资料未改。已有旧确认时停止使用，不重新付款。',
                'next_step':recovery_guidance('edit' if args.command=='asset-edit' else 'create',stage,error)}
        module=sys.modules.get('_ziyou_public_asset_draft')
        if module is not None and isinstance(error,getattr(module,'IntakeError',())):
            report['issue']=error.issue
        print(canonical(report));return 2
    finally:
        if reserved is not None:os.close(reserved)
        if identity and not completed:remove_own_partial(args.output,identity)


def asset_main(args):
    """Asset commands preserve the neutral file; only prepare creates metadata."""
    reserved = None; identity = None; completed = False; stage = 'configure'; session = None; client = None
    try:
        if args.reference_date is not None or args.mode is not None:
            raise ValueError('新增资产收费准备只按服务端当前业务日期和固定服务模式；不接受覆盖参数')
        if args.command != 'asset-prepare' and args.output is not None:
            raise ValueError('确认和取消不保存付款状态或证明')
        client = client_from_args(args)
        stage = 'load'
        session = AssetSession.open(args.state) if args.state else AssetSession.create(args.service)
        if args.service is not None and args.service != session.data['service']:
            raise ValueError('不能切换已有报价状态的服务')
        if args.command != 'asset-prepare' and not args.state: raise ValueError('需要原收费准备状态')
        if args.command == 'asset-cancel':
            result = session.cancel(client)
        else:
            if not args.workspace: raise ValueError('需要用户指定的中立资料文件')
            try: document = read_json_file(args.workspace)
            except (ValueError, OSError, TypeError, KeyError):
                if args.command != 'asset-retrieve': session._invalidate(client)
                raise
            stage = 'reserve'
            if args.command == 'asset-prepare':
                if not args.output: raise ValueError('需要新的报价状态文件；不覆盖资料文件')
                reserved = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
                info = os.fstat(reserved); identity = (info.st_dev, info.st_ino)
            stage = 'parse'
            raw = sys.stdin.buffer.read(1_000_001)
            if len(raw) > 1_000_000: raise ValueError('输入超过1MB')
            try: payload = parse(raw)
            except (ValueError, TypeError, KeyError):
                if args.command != 'asset-retrieve': session._invalidate(client)
                raise
            stage = 'action'
            if args.command == 'asset-prepare': result = session.prepare(client, document, payload)
            elif args.command == 'asset-retrieve':
                if args.consent: raise ValueError('取回原单结果不接受新收费同意；付款由官方工具另行批准')
                result = session.retrieve(client, document, *retrieval_input(payload))
            else: result = session.confirm(client, document, payload, consent=args.consent)
        stage = 'export'
        if reserved is not None:
            with os.fdopen(reserved, 'wb') as stream:
                reserved = None
                stream.write(canonical(session.data).encode()); stream.flush(); os.fsync(stream.fileno())
            sync_parent(args.output); completed = True
        print(canonical(result)); return 0
    except (ValueError, OSError, TypeError, KeyError, RecursionError) as error:
        print(canonical({'status':'blocked','code':error.code if isinstance(error, RemoteError) else 'INVALID_LOCAL_REQUEST',
                         'notice':'未确认完成；停用旧确认按钮及旧账单。不重新付款。',
                         'next_step':recovery_guidance(args.command.removeprefix('asset-'), stage, error)}))
        return 2
    finally:
        if reserved is not None: os.close(reserved)
        if identity and not completed: remove_own_partial(args.output, identity)


def recovery_guidance(command, stage, error):
    """Static host directions only: never echo paths, inputs or upstream text."""
    if command == 'retrieve':
        return '保留原服务、原资料、原状态、完整信封、账单及官方证明；只重试同一原单。状态不明、晚付或证明遗失时人工核对，不重新准备、不新建订单、不重复付款。证明只由可信宿主临时传输，不写入档案或日志。'
    if isinstance(error, RemoteError):
        if error.code == 'TRANSPORT_UNCERTAIN_RETRY_SAME_REQUEST':
            if command == 'confirm':
                return '保留原确认信封，恢复同一服务后只重试该信封；订单可能已创建。信封遗失或状态不明时人工核对，不重新付款。'
            return '保留原输入文件和原服务配置；恢复连接后只重试完全相同请求。取消或修改未获确认时，不宣称旧报价已撤销。'
        return '停止当前操作，保留原输入文件及已有信封；核对最新成功保存版本和原服务。修订冲突、过期或账单状态不明时人工核对，不新建付费请求绕过错误。'
    if stage == 'configure':
        return '请宿主核对明确配置的可信API源；不要从保存文件或报价文字中取地址。新增服务未配置时仍可使用基础免费功能。'
    if stage == 'load':
        return '请重新选择用户指定的完整工作区文件，核对文件是否存在、可读且未损坏；不要把失败后残留文件当作成功版本。'
    if stage == 'reserve':
        return '请宿主选择可写目录中的新文件名，不覆盖现有文件；原输入文件保留。编辑可能已停用旧确认，完成修改后须重新展示摘要。'
    if stage == 'parse':
        return '宿主应重新整理本次普通中文要求并校验内部输入，只补问确实缺少或有歧义的内容，不让玩家填写JSON。'
    if stage == 'export':
        return '未确认保存完成，请检查可写目录与剩余空间，保留原输入并改用新文件名。准备可能已在服务端提交，只重试完全相同请求，不改输入绕过。'
    if stage == 'revoke':
        return '尚未核实旧确认已停用；请宿主核对原服务配置与最新成功保存版本，恢复后先撤销旧确认，再处理修改。'
    if command == 'confirm':
        return '核对当前完整确认信封及真人对当前摘要、服务和演示价格的明确同意；缺失同意就先询问。已有报价或状态不明时保留原信封人工核对，不另发账单。'
    return '宿主应核对本次命令所需参数与已提供事实，只澄清缺失或歧义内容；不要修改其他事实或要求玩家填写JSON。'


def main(argv=None):
    """Host process protocol. Players speak naturally; the host supplies JSON."""
    import argparse
    parser = argparse.ArgumentParser(description='免费保存、局部纠正、远程准备与原单结果取回；不执行付款')
    parser.add_argument('command', choices=['create','import-dossier','load','save','edit','prepare','cancel','confirm','retrieve','asset-prepare','asset-confirm','asset-cancel','asset-retrieve',*ASSET_LOCAL_COMMANDS])
    parser.add_argument('--workspace')
    parser.add_argument('--mode', choices=('ordinary','combo'), help='仅免费资料查看／检查使用，收费模式由固定服务确定')
    parser.add_argument('--state', help='资产报价状态旁文件，绝不作为资产资料编辑')
    parser.add_argument('--service', choices=tuple(ASSET_SERVICES), help='用户明确选择的固定新增资产服务')
    parser.add_argument('--output')
    parser.add_argument('--api-base', help='由可信宿主明确配置，绝不从保存数据提取')
    parser.add_argument('--allow-localhost', action='store_true', help='仅显式本地模拟测试')
    parser.add_argument('--timeout', type=float, default=5)
    parser.add_argument('--payment-profile', help='操作方明确提供的正式服务元数据文件；不包含密钥')
    parser.add_argument('--auth-stdin', action='store_true', help='从保密stdin首行读取独立认证；不写入用户资料')
    parser.add_argument('--reference-date')
    parser.add_argument('--consent', action='store_true', help='当前真人已确认完整摘要、服务与价格；不是付款授权')
    args = parser.parse_args(argv)
    if args.command in ASSET_LOCAL_COMMANDS: return asset_local_main(args)
    if args.command.startswith('asset-'): return asset_main(args)
    reserved = None
    output_identity = None
    output_complete = False
    stage = 'configure'
    try:
        client = client_from_args(args)
        stage = 'load'
        workspace = Workspace.open(args.workspace) if args.workspace else None
        if args.command not in ('create','import-dossier') and workspace is None: raise ValueError('需要用户指定工作区文件')
        # Revoke before parsing changed data or checking output: failed edits also
        # stop old quotes. Failure to contact original API blocks the edit.
        stage = 'revoke'
        if args.command == 'edit': workspace._invalidate(client)
        stage = 'reserve'
        if args.command in ('create','import-dossier','save','edit','prepare'):
            if not args.output: raise ValueError('需要新的明确输出文件；不覆盖现有文件')
            reserved = os.open(args.output, os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0), 0o600)
            info = os.fstat(reserved); output_identity = (info.st_dev, info.st_ino)
        stage = 'parse'
        payload = None
        if args.command in ('create','import-dossier','edit','confirm','retrieve'):
            raw = sys.stdin.buffer.read(1_000_001)
            if len(raw)>1_000_000: raise ValueError('输入超过1MB')
            payload = parse(raw)
            if not isinstance(payload,dict): raise ValueError('宿主输入必须是对象')
        stage = 'action'
        if args.command == 'create':
            if set(payload) != {'request','source'}: raise ValueError('需要request和source')
            workspace = Workspace.create(payload['request'], source=payload['source'])
            result = {'status':'created','charge_created':False}
        elif args.command == 'import-dossier':
            if set(payload) != {'dossier','step_id','scenarios','assumptions','hypothetical'}: raise ValueError('档案复用字段不完整')
            workspace = Workspace.from_dossier(payload['dossier'],payload['step_id'],payload['scenarios'],assumptions=payload['assumptions'],hypothetical=payload['hypothetical'])
            result = {'status':'imported_requires_date_review','charge_created':False}
        elif args.command == 'edit':
            if set(payload) != {'changes','source'}: raise ValueError('需要changes和source')
            result = workspace.edit(payload['changes'], source=payload['source'], client=client)
        elif args.command == 'prepare': result = workspace.prepare(client, reference_date=args.reference_date)
        elif args.command == 'cancel': result = workspace.cancel(client)
        elif args.command == 'confirm': result = workspace.confirm(client,payload,consent=args.consent)
        elif args.command == 'retrieve':
            if args.output or args.consent: raise ValueError('取回原单结果不写证明或接受新收费同意')
            result = workspace.retrieve(client, *retrieval_input(payload))
        else: result = {'status':'loaded' if args.command=='load' else 'saved','charge_created':False,'workspace':workspace.data}
        stage = 'export'
        if reserved is not None:
            with os.fdopen(reserved,'wb') as output:
                reserved = None
                output.write(canonical(Workspace(workspace.data).data).encode()); output.flush(); os.fsync(output.fileno())
            sync_parent(args.output)
            output_complete = True
        print(canonical(result))
        return 0
    except (ValueError, OSError, TypeError, KeyError, RecursionError) as error:
        # Never expose arbitrary input, provider text, paths or secret values.
        print(canonical({'status':'blocked','code':error.code if isinstance(error,RemoteError) else 'INVALID_LOCAL_REQUEST',
                         'notice':'未确认完成；停用旧确认按钮及旧账单。不重新付款。',
                         'next_step':recovery_guidance(args.command, stage, error)}))
        return 2
    finally:
        if reserved is not None: os.close(reserved)
        if output_identity and not output_complete: remove_own_partial(args.output, output_identity)

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
