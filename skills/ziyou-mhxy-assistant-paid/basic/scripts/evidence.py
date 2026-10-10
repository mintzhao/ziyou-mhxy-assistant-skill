#!/usr/bin/env python3
"""Validate explicit evidence attribution, not the truth or meaning of quoted text.

The host prepares this small ledger from the conversation. No NLP, network, or
independent factual verification is performed. Examples cannot confirm owned state.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
try:
    from . import decisions
except ImportError:
    import decisions

ORIGINS = ('user', 'external', 'official_reference', 'demonstration')
SCOPES = ('current_account', 'current_item', 'candidate', 'general_rule', 'example', 'scenario')
STATUSES = ('confirmed', 'conditional', 'unknown', 'conflicting')


def pointer(value, path):
    if not isinstance(path, str) or not path.startswith('/') or len(path) > 500:
        raise ValueError('Input binding needs a nonempty JSON pointer')
    for token in path[1:].split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        if isinstance(value, list):
            if not token.isdigit() or str(int(token)) != token:
                raise ValueError('Invalid list pointer')
            try: value = value[int(token)]
            except IndexError: raise ValueError('Input pointer does not exist') from None
        elif isinstance(value, dict) and token in value:
            value = value[token]
        else:
            raise ValueError('Input pointer does not exist')
    return value


def validate_ledger(data):
    decisions.fields(data, ('sources', 'facts'), ('bindings', 'calculation_input'))
    sources = {}; facts = {}; warnings = []
    for source in decisions.rows(data['sources'], 'sources'):
        decisions.fields(source, ('id', 'origin', 'text'), ('url',))
        ident = decisions.text(source['id'], 'source id', 80)
        if ident in sources: raise ValueError('Duplicate source id')
        if source['origin'] not in ORIGINS: raise ValueError('Invalid evidence origin')
        # Multiline conversation text is allowed; no execution or markup rendering.
        if not isinstance(source['text'], str) or not source['text'].strip() or len(source['text']) > 20000 or '\x00' in source['text']:
            raise ValueError('Source text must be bounded nonempty text')
        if 'url' in source: decisions.text(source['url'], 'source URL', 2000)
        sources[ident] = source
    for fact in decisions.rows(data['facts'], 'facts'):
        decisions.fields(fact, ('id', 'label', 'scope', 'status', 'value', 'evidence'), ('assumption',))
        ident = decisions.text(fact['id'], 'fact id', 80)
        if ident in facts: raise ValueError('Duplicate fact id')
        decisions.text(fact['label'], 'fact label', 200)
        if fact['scope'] not in SCOPES or fact['status'] not in STATUSES: raise ValueError('Invalid fact scope/status')
        if isinstance(fact['value'], (dict, list, float)) or (fact['value'] is not None and not isinstance(fact['value'], (str, int, bool))):
            raise ValueError('Fact value must be a scalar, decimal text, or null')
        if isinstance(fact['value'], str) and len(fact['value']) > 1000: raise ValueError('Fact value too long')
        evidence = decisions.rows(fact['evidence'], 'fact evidence')
        origins = set()
        for cited in evidence:
            decisions.fields(cited, ('source_id', 'excerpt'))
            if cited['source_id'] not in sources: raise ValueError('Unknown cited source')
            if not isinstance(cited['excerpt'], str) or not cited['excerpt'].strip() or len(cited['excerpt']) > 4000:
                raise ValueError('Excerpt must be nonempty bounded verbatim text')
            source = sources[cited['source_id']]
            if cited['excerpt'] not in source['text']: raise ValueError('Excerpt is not verbatim in cited source')
            origins.add(source['origin'])
        if fact['status'] == 'confirmed':
            if fact['value'] is None or not evidence: raise ValueError('Confirmed facts require a value and evidence')
            if fact['scope'] in ('current_account', 'current_item') and (origins != {'user'}):
                raise ValueError('Owned account/item state must come from explicit user evidence, not references or demonstrations')
            if fact['scope'] == 'example': raise ValueError('An example is never a confirmed account fact; use conditional')
        elif fact['status'] == 'conditional':
            decisions.text(fact.get('assumption'), 'explicit assumption', 1000)
        elif fact['value'] is not None:
            raise ValueError('Unknown/conflicting facts must have null value; preserve possibilities in evidence')
        facts[ident] = fact
    bindings = []; used_paths = set()
    for binding in decisions.rows(data.get('bindings', []), 'bindings'):
        decisions.fields(binding, ('path', 'fact_id'))
        path = binding['path']; fid = binding['fact_id']
        if fid not in facts: raise ValueError('Binding references unknown fact')
        if path in used_paths: raise ValueError('Duplicate input binding')
        used_paths.add(path)
        fact = facts[fid]
        if fact['status'] not in ('confirmed', 'conditional'): raise ValueError('Unknown or conflicting fact cannot populate a calculator')
        if 'calculation_input' not in data: raise ValueError('Bindings need calculation_input')
        actual = pointer(data['calculation_input'], path)
        # Do not coerce strings, booleans, currency, or units at this boundary.
        if type(actual) is not type(fact['value']) or actual != fact['value']:
            raise ValueError('Bound calculator value differs from evidence fact')
        bindings.append({'path': path, 'fact_id': fid, 'status': fact['status'], 'scope': fact['scope'],
                         'assumption': fact.get('assumption')})
    conditional = [f for f in facts.values() if f['status'] == 'conditional']
    unresolved = [f for f in facts.values() if f['status'] in ('unknown', 'conflicting')]
    if conditional: warnings.append('Conditional values must remain visibly conditional in the answer and report')
    warnings.append('This validates attribution structure and exact copied values only; a host must still check that the excerpt actually supports the meaning, object, unit, and date')
    warnings.append('A user message may quote an example or somebody else; tag that passage as demonstration/external rather than treating every sentence as owned state')
    return {'calculator': 'evidence_ledger', 'status': 'attribution_structure_valid',
            'confirmed': [f for f in facts.values() if f['status'] == 'confirmed'],
            'conditional': conditional, 'unresolved': unresolved, 'validated_bindings': bindings,
            'unbound_input_not_verified': True, 'warnings': warnings}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input'); parser.add_argument('--output')
    args = parser.parse_args(argv)
    try:
        result = validate_ledger(decisions.read_input(args.input))
        output = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
        if args.output:
            with Path(args.output).open('x', encoding='utf-8') as file: file.write(output)
        else: sys.stdout.write(output)
    except (ValueError, OSError, TypeError, RecursionError) as error:
        parser.error(str(error))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
