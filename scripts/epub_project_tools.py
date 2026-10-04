#!/usr/bin/env python3
"""Offline EPUB translation helpers; Python 3.9+, standard library only."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import stat
import sys
import tempfile
from typing import Iterable
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET
import zipfile
import zlib

WORK_HEADER_PREFIXES = ('原文标题：', '来源文件：', '来源 EPUB：')
TEXT_EXTENSIONS = {'.xhtml', '.html', '.htm'}
OPF = 'http://www.idpf.org/2007/opf'
DC = 'http://purl.org/dc/elements/1.1/'
CONTAINER = 'urn:oasis:names:tc:opendocument:xmlns:container'
XHTML = 'http://www.w3.org/1999/xhtml'
XML_ID = '{http://www.w3.org/XML/1998/namespace}id'
MAX_ENTRIES = 10000
MAX_ENTRY_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024


def read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8-sig')


def write_text(path: Path, text: str, force: bool = False) -> None:
    """Publish complete UTF-8 output; exclusive creation unless explicitly replacing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not force:
        with path.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
        return
    fd, temp = tempfile.mkstemp(prefix='.' + path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def ensure_distinct(output: Path, inputs: Iterable[Path]) -> None:
    resolved = output.resolve()
    for source in inputs:
        if resolved == source.resolve() or (output.exists() and source.exists() and os.path.samefile(output, source)):
            raise ValueError('Output must not overwrite an input, even with --force')


def numbered_markdown_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        raise ValueError(f'Translation folder does not exist: {folder}')
    files = [p for p in folder.iterdir() if p.is_file() and re.match(r'^\d+_.+\.md$', p.name, re.I)]
    numbers = [int(p.name.split('_', 1)[0]) for p in files]
    if len(numbers) != len(set(numbers)):
        raise ValueError('Duplicate chapter numbers; resolve them before merging')
    return sorted(files, key=lambda p: int(p.name.split('_', 1)[0]))


def strip_work_headers(markdown: str) -> str:
    """Only remove a recognized leading traceability block, never body separators."""
    lines = markdown.replace('\r\n', '\n').replace('\r', '\n').splitlines(keepends=True)
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and re.match(r'^#\s+', lines[i]):
        i += 1
    start = i
    seen = False
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
        elif line.startswith(WORK_HEADER_PREFIXES):
            seen = True
            i += 1
        elif line == '---' and seen:
            i += 1
            break
        else:
            break
    if seen:
        lines[start:i] = ['\n']
    return ''.join(lines).strip('\n') + '\n'


def merge_command(args: argparse.Namespace) -> int:
    source, output = Path(args.input), Path(args.output)
    files = numbered_markdown_files(source)
    ensure_distinct(output, files)
    warnings = []
    if args.skip_first and files:
        warnings.append('First numbered file explicitly excluded; verify it contains no reader-facing content')
        files = files[1:]
    if not files:
        raise ValueError(f'No numbered Markdown files found in {source}')
    nums = [int(p.name.split('_', 1)[0]) for p in files]
    gaps = [f'{left + 1}-{right - 1}' if right - left > 2 else str(left + 1)
            for left, right in zip(nums, nums[1:]) if right - left > 1]
    if gaps and not args.allow_gaps:
        raise ValueError(f'Missing chapter numbers: {gaps}; use --allow-gaps only for reviewed exclusions')
    chunks = []
    for path in files:
        chunk = strip_work_headers(read_text(path))
        if not chunk.strip():
            raise ValueError(f'Empty chapter: {path.name}')
        chunks.append(chunk.rstrip('\n'))
    write_text(output, '\n\n'.join(chunks) + '\n', args.force)
    print(json.dumps({'files': len(files), 'chapters': [p.name for p in files],
                      'gaps': gaps, 'output': str(output), 'warnings': warnings}, ensure_ascii=True, indent=2))
    return 0


def is_protected_markdown_block(block: str) -> bool:
    """Conservative plain-prose-only policy, not a complete Markdown parser."""
    lines = block.splitlines()
    if not block.strip():
        return True
    if any(line.startswith(('    ', '\t')) or re.match(r'^\s*(?:[#>|]|[-+*]\s|\d+[.)]\s)', line) for line in lines):
        return True
    # Preserve inline syntax too: splitting it can change emphasis, links or math.
    if re.search(r'[`~$*_<>{}\[\]\\|]|https?://|\bISBN\b|\S+@\S+', block, re.I):
        return True
    if any(re.fullmatch(r'\s*[=-]+\s*', line) for line in lines):
        return True
    if any(line.endswith('  ') for line in lines):
        return True
    return False


def markdown_blocks(text: str):
    """Keep fenced code, display math and raw HTML intact across blank lines."""
    front = re.match(r'\A---[^\S\n]*\n.*?^(?:---|\.\.\.)[^\S\n]*(?:\n|$)', text, re.S | re.M)
    if front:
        yield front[0], True
        text = text[front.end():]
    elif text.startswith('---\n'):
        yield text, True
        return
    current = []
    indented = False
    fence = None
    math_close = None
    html = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if fence:
            current.append(line)
            if re.fullmatch(re.escape(fence[0]) + '{' + str(fence[1]) + r',}\s*', stripped):
                fence = None
            continue
        if math_close:
            current.append(line)
            if stripped == math_close:
                math_close = None
            continue
        if html:
            current.append(line)
            continue
        if indented:
            if not stripped or line.startswith(('    ', '\t')):
                current.append(line)
                continue
            yield ''.join(current), True
            current = []
            indented = False
        if line.startswith(('    ', '\t')):
            if current:
                yield ''.join(current), True
            current = [line]
            indented = True
            continue
        match = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if match:
            if current:
                yield ''.join(current), True
                current = []
            fence = (match[1][0], len(match[1]))
            current.append(line)
            continue
        if stripped in ('$$', r'\['):
            if current:
                yield ''.join(current), True
                current = []
            math_close = '$$' if stripped == '$$' else r'\]'
            current.append(line)
            continue
        if stripped.startswith('<'):
            html = True
        # Raw HTML is conservatively protected until the rest of the document;
        # ambiguous block boundaries must not silently damage markup.
        if not stripped and not html:
            if current:
                block = ''.join(current)
                yield block, is_protected_markdown_block(block)
                current = []
        else:
            current.append(line)
    if current:
        block = ''.join(current)
        yield block, bool(fence or math_close or html) or is_protected_markdown_block(block)


def split_paragraph(text: str, target_min: int, target_max: int) -> list[str]:
    if not 1 <= target_min <= target_max:
        raise ValueError('Require 1 <= target-min <= target-max')
    # Work with indexes, avoiding variable-width lookbehind and preserving spaces.
    ends = [m.end() for m in re.finditer(r'[。！？；.!?;][”’」』》）】"\']*(?:\s+|(?=[^\x00-\x7f])|$)', text)]
    pieces = []
    start = 0
    while len(text) - start > target_max:
        candidates = [i for i in ends if start + target_min <= i <= start + target_max]
        if candidates:
            end = max(candidates)
        else:
            window = text[start:start + target_max]
            boundaries = [m.end() + start for m in re.finditer(r'\s+|[，、,]', window)]
            boundaries = [i for i in boundaries if i >= start + target_min]
            if boundaries:
                end = max(boundaries)
            else:
                cjk = [i for i in range(start + target_min, start + target_max + 1)
                       if re.match(r'[\u3400-\u9fff]', text[i-1]) and
                       i < len(text) and re.match(r'[\u3400-\u9fff]', text[i])]
                if not cjk:
                    # Never cut a long Latin word, identifier or unknown script blindly.
                    break
                end = max(cjk)
        pieces.append(text[start:end])
        start = end
    pieces.append(text[start:])
    return [piece for piece in pieces if piece]


def mobile_command(args: argparse.Namespace) -> int:
    if not 1 <= args.target_min <= args.target_max <= args.threshold:
        raise ValueError('Require 1 <= target-min <= target-max <= threshold')
    source, output = Path(args.input), Path(args.output)
    ensure_distinct(output, [source])
    text = read_text(source).replace('\r\n', '\n').replace('\r', '\n')
    out, unresolved = [], []
    split_blocks = protected = 0
    for index, (block, protect) in enumerate(markdown_blocks(text), 1):
        if protect:
            protected += 1
            out.append(block.rstrip('\n'))
        elif len(block.strip()) <= args.threshold:
            out.append(block.strip())
        else:
            pieces = split_paragraph(block.strip(), args.target_min, args.target_max)
            split_blocks += int(len(pieces) > 1)
            out.extend(piece.strip() for piece in pieces)
            if any(len(piece.strip()) > args.threshold for piece in pieces):
                unresolved.append(index)
    rendered = '\n\n'.join(out) + '\n'
    if re.sub(r'\s', '', text) != re.sub(r'\s', '', rendered):
        raise ValueError('Mobile transformation changed non-whitespace content')
    write_text(output, rendered, args.force)
    print(json.dumps({'input': str(source), 'output': str(output), 'split_blocks': split_blocks,
                      'protected_blocks': protected, 'unresolved_blocks': unresolved,
                      'warnings': ['Some long prose remains; review manually'] if unresolved else []},
                     ensure_ascii=True, indent=2))
    return 1 if unresolved else 0


def local_name(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def normalize_href(base: str, href: str) -> str | None:
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc:
        return None
    path = unquote(parsed.path)
    if not path:
        return base
    if path.startswith('/') or '\\' in path or '\x00' in path:
        raise ValueError(f'Unsafe archive reference: {href}')
    target = posixpath.normpath(posixpath.join(posixpath.dirname(base), path))
    if target in ('', '.', '..') or target.startswith('../'):
        raise ValueError(f'Reference escapes archive root: {href}')
    return target


def text_from_element(element: ET.Element) -> str:
    if local_name(element.tag) in ('head', 'nav', 'script', 'style'):
        return ''
    parts = [element.text or '']
    for child in element:
        parts.append(text_from_element(child))
        parts.append(child.tail or '')
    return ''.join(parts)


class EpubPackage:
    def __init__(self, path: Path):
        self.path = path
        self.zf = zipfile.ZipFile(path)
        try:
            infos = self.zf.infolist()
            names = [i.filename for i in infos]
            if len(infos) > MAX_ENTRIES or sum(i.file_size for i in infos) > MAX_TOTAL_BYTES:
                raise ValueError('Archive exceeds file-count or uncompressed-size limit')
            if len(names) != len(set(names)):
                raise ValueError('Duplicate ZIP entry names')
            for info in infos:
                parts = info.filename.rstrip('/').split('/')
                if (info.filename.startswith('/') or '\\' in info.filename or '..' in parts
                        or '.' in parts or ':' in parts[0] or '\x00' in info.filename):
                    raise ValueError('Unsafe ZIP entry: ' + info.filename)
                if info.file_size > MAX_ENTRY_BYTES:
                    raise ValueError('ZIP entry exceeds size limit: ' + info.filename)
                if info.flag_bits & 1 or stat.S_ISLNK(info.external_attr >> 16):
                    raise ValueError('Encrypted ZIP entry or symlink is unsupported: ' + info.filename)
            self.names = set(names)
            self.cache = {}
            container = self.xml('META-INF/container.xml')
            rootfiles = container.findall('.//{' + CONTAINER + '}rootfile')
            if not rootfiles:
                raise ValueError('container.xml has no rootfile')
            self.multiple_renditions = len(rootfiles) > 1
            self.opf_path = normalize_href('', rootfiles[0].get('full-path', ''))
            if not self.opf_path:
                raise ValueError('Invalid OPF rootfile path')
            self.opf = self.xml(self.opf_path)
            if self.opf.tag != '{' + OPF + '}package':
                raise ValueError('Invalid OPF package root/namespace')
            self.items = self.opf.findall('./{' + OPF + '}manifest/{' + OPF + '}item')
            ids = [i.get('id') for i in self.items]
            if not ids or any(not i for i in ids) or len(ids) != len(set(ids)):
                raise ValueError('Manifest missing or contains empty/duplicate IDs')
            self.manifest = {i.get('id'): i for i in self.items}
            self.spine = self.opf.find('./{' + OPF + '}spine')
            if self.spine is None or not list(self.spine):
                raise ValueError('Missing or empty spine')
            self.ordered = []
            for ref in self.spine:
                item = self.manifest.get(ref.get('idref'))
                if item is None:
                    raise ValueError('Spine references missing manifest ID: ' + str(ref.get('idref')))
                target = normalize_href(self.opf_path, item.get('href', ''))
                if target is None or target not in self.names:
                    raise ValueError('Spine resource is missing or remote: ' + str(target))
                self.ordered.append({'idref': ref.get('idref'), 'path': target,
                                     'linear': ref.get('linear', 'yes'),
                                     'media_type': item.get('media-type', ''),
                                     'properties': item.get('properties', '').split()})
        except Exception:
            self.zf.close()
            raise

    def close(self):
        self.zf.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def xml(self, name: str) -> ET.Element:
        if name not in self.cache:
            data = self.zf.read(name)
            # ET never fetches external entities; reject internal entity declarations too.
            if b'<!ENTITY' in data.upper() or b'\x00' in data:
                raise ValueError('Entity declarations or non-UTF-8 XML unsupported: ' + name)
            self.cache[name] = ET.fromstring(data)
        return self.cache[name]

    def metadata(self):
        return {key: self.opf.findtext('.//{' + DC + '}' + key, default='')
                for key in ('title', 'creator', 'language', 'identifier')}

    def reading_text(self):
        parts = []
        for item in self.ordered:
            if item['media_type'] != 'application/xhtml+xml':
                raise ValueError('Text comparison requires XHTML spine; unsupported: ' + item['path'])
            root = self.xml(item['path'])
            body = root.find('.//{' + XHTML + '}body')
            if body is None:
                raise ValueError('XHTML body missing: ' + item['path'])
            parts.append(text_from_element(body))
        return '\n'.join(parts)


def inspect_command(args):
    report = {'epub': args.epub, 'errors': [], 'warnings': []}
    try:
        with EpubPackage(Path(args.epub)) as package:
            for item in package.ordered:
                item['sha256'] = hashlib.sha256(package.zf.read(item['path'])).hexdigest()
            report.update({'opf_path': package.opf_path, 'metadata': package.metadata(),
                           'spine': package.ordered, 'manifest_items': len(package.items)})
            if package.multiple_renditions:
                report['warnings'].append('Multiple renditions: only first rootfile inspected')
            if 'META-INF/encryption.xml' in package.names:
                report['warnings'].append('Encryption declarations present; inspect algorithms before conversion (may be font obfuscation)')
        report['sha256'] = file_hash(Path(args.epub))
    except (OSError, ValueError, KeyError, ET.ParseError, zipfile.BadZipFile, RuntimeError, zlib.error) as exc:
        report['errors'].append(str(exc))
    return write_report(args, report, int(bool(report['errors'])))


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def qc_command(args):
    report = {'epub': args.epub, 'errors': [], 'warnings': [], 'broken_images': [],
              'broken_links': [], 'forbidden_hits': [], 'long_paragraphs': []}
    errors, warnings = report['errors'], report['warnings']
    try:
        with EpubPackage(Path(args.epub)) as package:
            infos = package.zf.infolist()
            if not infos or infos[0].filename != 'mimetype' or infos[0].compress_type != zipfile.ZIP_STORED:
                errors.append('mimetype must be the first uncompressed ZIP entry')
            if package.zf.read('mimetype') != b'application/epub+zip':
                errors.append('Invalid mimetype content')
            if infos and infos[0].filename == 'mimetype' and infos[0].extra:
                errors.append('mimetype ZIP entry has extra fields')
            report.update({'metadata': package.metadata(), 'opf_path': package.opf_path,
                           'zip_entries': len(infos), 'spine': package.ordered})
            for key in ('title', 'language', 'identifier'):
                if not report['metadata'][key].strip():
                    errors.append('Required metadata missing: ' + key)
            unique = package.opf.get('unique-identifier')
            identifiers = package.opf.findall('.//{' + DC + '}identifier')
            if not unique or not any(i.get('id') == unique and (i.text or '').strip() for i in identifiers):
                errors.append('unique-identifier does not resolve to a nonempty dc:identifier')
            if not report['metadata']['creator'].strip():
                warnings.append('No creator metadata; optional in EPUB, verify against source')
            if package.multiple_renditions:
                warnings.append('Only first rendition checked')
            if 'META-INF/encryption.xml' in package.names:
                warnings.append('Encryption declarations present; encrypted resources are not fully validated')
            nav_items = [i for i in package.items if 'nav' in i.get('properties', '').split()]
            if package.opf.get('version', '').startswith('3'):
                if len(nav_items) != 1:
                    errors.append('EPUB 3 must have one manifest nav item')
                elif nav_items[0].get('media-type') != 'application/xhtml+xml':
                    errors.append('EPUB navigation item must be XHTML')
                else:
                    nav_path = normalize_href(package.opf_path, nav_items[0].get('href', ''))
                    nav_root = package.xml(nav_path)
                    if not any('toc' in n.get('{http://www.idpf.org/2007/ops}type', '').split()
                               for n in nav_root.iter('{' + XHTML + '}nav')):
                        errors.append('Navigation document has no toc nav')
            elif package.opf.get('version', '').startswith('2'):
                ncx = package.manifest.get(package.spine.get('toc'))
                if ncx is None or ncx.get('media-type') != 'application/x-dtbncx+xml':
                    errors.append('EPUB 2 spine toc does not reference NCX')
            else:
                errors.append('Unsupported package version')
            for item in package.items:
                href = item.get('href', '')
                if not href:
                    errors.append('Manifest item has no href: ' + str(item.get('id')))
                    continue
                target = normalize_href(package.opf_path, href)
                if target is None:
                    warnings.append('Remote manifest resource not fetched: ' + href)
                elif target not in package.names:
                    errors.append('Manifest resource missing: ' + target)
            roots, ids = {}, {}
            media_types = {normalize_href(package.opf_path, item.get('href', '')): item.get('media-type', '')
                           for item in package.items}
            xml_types = {'application/xhtml+xml', 'image/svg+xml', 'application/x-dtbncx+xml'}
            for name in sorted(package.names):
                if media_types.get(name) in xml_types or Path(name).suffix.lower() in TEXT_EXTENSIONS | {'.svg', '.ncx'}:
                    try:
                        root = package.xml(name)
                        roots[name] = root
                        if media_types.get(name) == 'application/xhtml+xml':
                            if root.tag != '{' + XHTML + '}html' or root.find('{' + XHTML + '}body') is None:
                                errors.append('Invalid XHTML root/body: ' + name)
                        values = [n.get('id') or n.get(XML_ID) for n in root.iter() if n.get('id') or n.get(XML_ID)]
                        ids[name] = set(values)
                        if any(count > 1 for count in Counter(values).values()):
                            errors.append('Duplicate XML IDs: ' + name)
                    except (ET.ParseError, ValueError) as exc:
                        errors.append(f'XML error: {name}: {exc}')
            report['xhtml_files'] = sum(media_types.get(n) == 'application/xhtml+xml' or Path(n).suffix.lower() in TEXT_EXTENSIONS for n in roots)
            image_refs = 0
            text = '\n'.join(text_from_element(r) for n, r in roots.items() if media_types.get(n) == 'application/xhtml+xml' or Path(n).suffix.lower() in TEXT_EXTENSIONS)
            for name, root in roots.items():
                for node in root.iter():
                    tag = local_name(node.tag)
                    if tag in ('p', 'div', 'li', 'dd', 'dt', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                        snippet = text_from_element(node).strip()
                        if snippet.startswith(WORK_HEADER_PREFIXES):
                            report['forbidden_hits'].append(snippet[:100])
                    refs = []
                    for attr in ('src', 'href', '{http://www.w3.org/1999/xlink}href', 'poster'):
                        if node.get(attr):
                            refs.append(node.get(attr))
                    if tag == 'object' and node.get('data'):
                        refs.append(node.get('data'))
                    if node.get('srcset'):
                        warnings.append('srcset needs EPUBCheck/manual validation: ' + name)
                    for href in refs:
                        target = normalize_href(name, href)
                        if target is None:
                            if tag not in ('a', 'content'):
                                warnings.append(f'External resource not fetched: {name} -> {href}')
                            continue
                        image_refs += int(tag in ('img', 'image'))
                        fragment = unquote(urlsplit(href).fragment)
                        problem = target not in package.names or (fragment and target in ids and fragment not in ids[target])
                        if problem:
                            key = 'broken_images' if tag in ('img', 'image') else 'broken_links'
                            report[key].append(f'{name} -> {href}')
                    if args.max_paragraph_chars and tag == 'p':
                        # Conservatively exempt nested math/code; tables are reported for review.
                        if not any(local_name(n.tag) in ('math', 'code', 'pre') for n in node.iter()):
                            size = len(re.sub(r'\s', '', text_from_element(node)))
                            if size > args.max_paragraph_chars:
                                report['long_paragraphs'].append({'file': name, 'characters': size})
            report['image_refs'] = image_refs
            report['forbidden_hits'] = list(dict.fromkeys(report['forbidden_hits']))
            for key in ('broken_images', 'broken_links', 'forbidden_hits'):
                if report[key]:
                    errors.append(f'{key}: {len(report[key])}')
            if report['long_paragraphs']:
                errors.append('Long paragraphs require review; see long_paragraphs')
            for needle in args.must_contain or []:
                if needle not in text:
                    errors.append('Missing required text: ' + needle)
            warnings.append('Partial QC only: use EPUBCheck and reader inspection for CSS, media, accessibility and full conformance')
    except (OSError, ValueError, KeyError, ET.ParseError, zipfile.BadZipFile, RuntimeError, zlib.error) as exc:
        errors.append(str(exc))
    return write_report(args, report, int(bool(errors)))


def compare_command(args):
    report = {'left': args.left, 'right': args.right, 'errors': [], 'warnings': []}
    try:
        texts = []
        for path in (args.left, args.right):
            with EpubPackage(Path(path)) as package:
                if package.multiple_renditions:
                    raise ValueError('Multiple renditions require manual comparison')
                texts.append(re.sub(r'\s', '', package.reading_text()))
        if not all(texts):
            raise ValueError('Cannot establish equivalence for empty body text')
        report['equal_ignoring_whitespace'] = texts[0] == texts[1]
        report['characters'] = [len(t) for t in texts]
        report['sha256'] = [hashlib.sha256(t.encode('utf-8')).hexdigest() for t in texts]
        if texts[0] != texts[1]:
            report['errors'].append('Spine body text differs (excluding navigation and whitespace)')
        report['warnings'].append('Text equivalence does not verify images, styling, reading usability or translation fidelity')
    except (OSError, ValueError, KeyError, ET.ParseError, zipfile.BadZipFile, RuntimeError, zlib.error) as exc:
        report['errors'].append(str(exc))
    return write_report(args, report, int(bool(report['errors'])))


def write_report(args, report, status):
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if getattr(args, 'json', None):
        sources = [Path(getattr(args, field)) for field in ('epub', 'left', 'right') if getattr(args, field, None)]
        ensure_distinct(Path(args.json), sources)
        write_text(Path(args.json), text + '\n', args.force)
    # ASCII-escaped console JSON also works in legacy Windows redirected pipes;
    # report files remain readable UTF-8. JSON consumers recover identical text.
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return status


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    merge = sub.add_parser('merge', help='Merge numerically ordered chapters; no silent omissions')
    merge.add_argument('--input', required=True)
    merge.add_argument('--output', required=True)
    merge.add_argument('--skip-first', action='store_true', help='Explicitly omit first numbered file; inspect it first')
    merge.add_argument('--allow-gaps', action='store_true', help='Allow reviewed gaps in chapter numbering')
    merge.set_defaults(func=merge_command)
    mobile = sub.add_parser('mobile', help='Conservatively split plain prose; preserve marked-up blocks')
    mobile.add_argument('--input', required=True)
    mobile.add_argument('--output', required=True)
    mobile.add_argument('--threshold', type=int, default=180)
    mobile.add_argument('--target-min', type=int, default=120)
    mobile.add_argument('--target-max', type=int, default=180)
    mobile.set_defaults(func=mobile_command)
    for name, function in [('inspect', inspect_command), ('qc', qc_command)]:
        child = sub.add_parser(name, help='Inspect spine' if name == 'inspect' else 'Partial EPUB package QC')
        child.add_argument('--epub', required=True)
        child.add_argument('--json')
        child.set_defaults(func=function)
        if name == 'qc':
            child.add_argument('--must-contain', action='append')
            child.add_argument('--max-paragraph-chars', type=int)
    compare = sub.add_parser('compare', help='Compare EPUB spine body text, ignoring whitespace')
    compare.add_argument('--left', required=True)
    compare.add_argument('--right', required=True)
    compare.add_argument('--json')
    compare.set_defaults(func=compare_command)
    for child in sub.choices.values():
        child.add_argument('--force', action='store_true', help='Replace an existing output, never an input')
    return parser


def main(argv: Iterable[str] | None = None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, 'max_paragraph_chars', None) is not None and args.max_paragraph_chars < 1:
        parser.error('--max-paragraph-chars must be positive')
    try:
        return args.func(args)
    except (OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({'errors': [str(exc)]}, ensure_ascii=True), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
