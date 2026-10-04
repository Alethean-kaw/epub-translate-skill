#!/usr/bin/env python3
"""Check this package's entry points, local documentation links and Python syntax."""
import ast
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
errors = []
text = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
front = re.match(r'\A---\n(.*?)\n---\n', text, re.S)
if not front:
    errors.append('SKILL.md must start with YAML frontmatter')
else:
    values = dict(re.findall(r'^(name|description):\s*(.+)$', front[1], re.M))
    if values.get('name') != 'epub-translate-skill':
        errors.append('Unexpected skill name')
    if not values.get('description'):
        errors.append('Skill description missing')

for path in [ROOT/'SKILL.md', ROOT/'README.md', ROOT/'README.zh-CN.md', *sorted((ROOT/'references').glob('*.md'))]:
    content = path.read_text(encoding='utf-8')
    for target in re.findall(r'\]\(([^)]+)\)', content):
        if '://' in target or target.startswith('#'):
            continue
        linked = path.parent / target.split('#', 1)[0]
        if not linked.exists():
            errors.append(f'{path.relative_to(ROOT)}: missing link {target}')

interface = (ROOT/'agents/openai.yaml').read_text(encoding='utf-8')
if '$epub-translate-skill' not in interface:
    errors.append('default_prompt must name $epub-translate-skill')
short = re.search(r'short_description:\s*"([^"]+)"', interface)
if not short or not 25 <= len(short[1]) <= 64:
    errors.append('short_description must contain 25–64 characters')
for folder in ('scripts', 'tests', 'tools'):
    for path in (ROOT/folder).glob('*.py'):
        try:
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except SyntaxError as exc:
            errors.append(str(exc))

for error in errors:
    print(error, file=sys.stderr)
if errors:
    raise SystemExit(1)
print('Skill metadata, local Markdown links and Python syntax OK')
