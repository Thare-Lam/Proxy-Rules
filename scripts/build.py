#!/usr/bin/env python3
"""Generate both clients from shared rules and an identical ruleset snapshot."""
import argparse
import concurrent.futures
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = 'https://raw.githubusercontent.com/LingJingMaster/Shadowrocket-Rules/refs/heads/main/'
SUPPORTED = {'DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD', 'IP-CIDR', 'IP-CIDR6', 'IP-ASN', 'GEOIP', 'DST-PORT', 'PROTOCOL', 'AND', 'OR', 'NOT', 'FINAL'}


def fields(line):
    parts, start, depth = [], 0, 0
    for i, char in enumerate(line):
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif char == ',' and depth == 0:
            parts.append(line[start:i].strip())
            start = i + 1
        if depth < 0:
            raise ValueError('Unbalanced rule: ' + line)
    if depth:
        raise ValueError('Unbalanced rule: ' + line)
    return parts + [line[start:].strip()]


def convert_expression(expression):
    parts = fields(expression)
    kind = parts[0]
    if kind not in SUPPORTED:
        raise ValueError('Unsupported rule type: ' + kind)
    if kind in {'AND', 'OR', 'NOT'}:
        inner = parts[1]
        if not (inner.startswith('(') and inner.endswith(')')):
            raise ValueError('Invalid logical rule')
        operands = fields(inner[1:-1])
        parts[1] = '(' + ','.join('(' + convert_expression(x[1:-1]) + ')' for x in operands) + ')'
    elif kind == 'PROTOCOL':
        if parts[1].lower() not in {'tcp', 'udp'}:
            raise ValueError('Unsupported protocol')
        parts[:2] = ['NETWORK', parts[1].lower()]
    elif kind == 'FINAL':
        parts[0] = 'MATCH'
    elif kind in {'IP-CIDR', 'IP-CIDR6'}:
        ipaddress.ip_network(parts[1], strict=False)
    return ','.join(parts)


def load_set(url):
    if url.startswith(UPSTREAM):
        filename = url[len(UPSTREAM):]
        if '/' in filename or not filename.endswith('.list'):
            raise ValueError('Invalid local ruleset path')
        content = (ROOT / filename).read_text()
    else:
        if not url.startswith('https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/'):
            raise ValueError('Review new ruleset source: ' + url)
        with urllib.request.urlopen(url, timeout=45) as response:
            content = response.read(20_000_001).decode('utf-8-sig')
        if len(content.encode()) > 20_000_000:
            raise ValueError('Ruleset exceeds size limit')
    lines = [x.strip() for x in content.splitlines() if x.strip() and not x.lstrip().startswith(('#', '//'))]
    if not lines or any('<html' in x.lower() for x in lines):
        raise ValueError('Empty or invalid ruleset: ' + url)
    return list(dict.fromkeys(lines))


def groups_for_mihomo(lines):
    output = [{'name': 'PROXY', 'type': 'select', 'include-all': True,
               'exclude-filter': '(?i)expire|reset|剩余|到期|流量|[0-9] G \\|', 'empty-fallback': 'REJECT'}]
    region_filters = []
    for line in lines:
        name, definition = line.split('=', 1)
        items = fields(definition.strip())
        options = [x for x in items[1:] if '=' not in x]
        parameters = dict(x.split('=', 1) for x in items[1:] if '=' in x)
        group = {'name': name.strip(), 'type': items[0]}
        if group['type'] not in {'select', 'url-test', 'fallback', 'load-balance'}:
            raise ValueError('Unsupported group type')
        if options:
            group['proxies'] = options
        for key in ('url', 'interval', 'tolerance', 'timeout'):
            if key in parameters:
                group[key] = parameters[key] if key == 'url' else int(parameters[key])
        if 'timeout' in group:
            group['timeout'] *= 1000
        default = parameters.get('policy-select-name')
        if default:
            if default not in options:
                raise ValueError('Unknown default selection')
            group['proxies'] = [default] + [x for x in options if x != default]
        pattern = parameters.get('policy-regex-filter')
        if pattern:
            group.update({'include-all': True, 'empty-fallback': 'REJECT'})
            if pattern.startswith('^((?!'):
                # The upstream other-region group uses negative lookahead; RE2 uses exclude-filter.
                if not region_filters:
                    raise ValueError('Other-region group requires preceding regions')
                group['exclude-filter'] = '|'.join(region_filters) + '|(?i:expire|reset|剩余|到期|流量|[0-9] G \\|)'
            else:
                if '(?' in pattern:
                    raise ValueError('Review region regex compatibility')
                group['filter'] = pattern
                region_filters.append(pattern)
        output.append(group)
    names = {x['name'] for x in output}
    if len(names) != len(output):
        raise ValueError('Duplicate group name')
    graph = {x['name']: x.get('proxies', []) for x in output}
    def visit(name, stack):
        if name in stack:
            raise ValueError('Group cycle: ' + name)
        for target in graph[name]:
            if target in graph:
                visit(target, stack | {name})
            elif target not in {'DIRECT', 'REJECT'}:
                raise ValueError('Unknown target: ' + target)
    for name in graph:
        visit(name, set())
    return output


def build(repository, output):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Expected owner/repository')
    source = json.loads((ROOT / 'source/routing.json').read_text())
    groups = groups_for_mihomo(source['groups'])
    targets = {x['name'] for x in groups} | {'DIRECT', 'REJECT'}
    rules = [fields(line) for line in source['rules']]
    urls = sorted({r[1] for r in rules if r[0] in {'RULE-SET', 'DOMAIN-SET'}})
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        snapshots = dict(zip(urls, pool.map(load_set, urls)))
    base = f'https://raw.githubusercontent.com/{repository}/release/'
    sr_rules, clash_rules, providers, files = [], [], {}, {}
    adaptations = []
    for rule in rules:
        policy_index = 1 if rule[0] == 'FINAL' else 2
        if rule[policy_index] not in targets:
            raise ValueError('Unknown policy: ' + rule[policy_index])
        if rule[0] in {'RULE-SET', 'DOMAIN-SET'}:
            lines = snapshots[rule[1]]
            if rule[0] == 'DOMAIN-SET':
                if any(',' in x or ' ' in x for x in lines):
                    raise ValueError('Invalid domain set')
                lines = [('DOMAIN-SUFFIX,' + x.lstrip('.')) if x.startswith('.') else ('DOMAIN,' + x) for x in lines]
            converted = []
            for entry in lines:
                if entry.startswith(('USER-AGENT,', 'URL-REGEX,')):
                    adaptations.append({'source': rule[1], 'rule': entry, 'reason': 'Shadowrocket HTTP matching has no Mihomo routing equivalent'})
                else:
                    converted.append(convert_expression(entry))
            if not converted:
                raise ValueError('Ruleset has no Mihomo-compatible entries')
            # Content-addressed sets keep old client configurations valid across releases.
            content = '\n'.join(lines) + '\n'
            digest = hashlib.sha256(content.encode()).hexdigest()
            filename = 'sets/' + digest + '.list'
            files[filename] = content
            provider = 'set-' + digest[:20]
            providers[provider] = {'type': 'inline', 'behavior': 'classical', 'payload': converted}
            sr_rules.append(','.join(['RULE-SET', base + filename, rule[2]] + rule[3:]))
            clash_rules.append(','.join(['RULE-SET', provider, rule[2]] + rule[3:]))
        else:
            sr_rules.append(','.join(rule))
            clash_rules.append(convert_expression(','.join(rule)))
    if rules[-1][0] != 'FINAL':
        raise ValueError('A final fallback is required')
    template = (ROOT / 'source/shadowrocket.conf').read_text()
    template = re.sub(r'^update-url\s*=.*$', 'update-url = ' + base + 'Shadowrocket.conf', template, flags=re.M)
    marker = '[Proxy]\n'
    template = template.replace(marker, marker + '\n[Proxy Group]\n' + '\n'.join(source['groups']) + '\n\n[Rule]\n' + '\n'.join(sr_rules) + '\n')
    files['Shadowrocket.conf'] = template
    # JSON is valid YAML 1.2 and supported by Mihomo and OpenClash's Ruby loader.
    overlay = {'proxy-groups': groups, 'rule-providers': providers, 'rules': clash_rules}
    files['OpenClash.yaml'] = json.dumps(overlay, ensure_ascii=False, indent=2) + '\n'
    files['conversion-report.json'] = json.dumps(adaptations, ensure_ascii=False, indent=2) + '\n'
    files['manifest.json'] = json.dumps({'repository': repository, 'files': {name: hashlib.sha256(files[name].encode()).hexdigest() for name in ('Shadowrocket.conf', 'OpenClash.yaml')}, 'rulesets': len(providers)}, indent=2) + '\n'
    for name, content in files.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)
    print(f'Generated both clients with {len(providers)} shared ruleset snapshots')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository', required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    build(args.repository, args.output)
