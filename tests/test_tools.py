"""Generated fixtures only: no third-party book content or remote services."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('epub_tools', ROOT / 'scripts/epub_project_tools.py')
tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools)


def epub(path, chapters=None, replacements=None, version='3.0', order=None):
    chapters = chapters or [('one', '<p>Original fixture paragraph.</p>')]
    manifest = ''.join(f'<item id="{name}" href="Text/{name}.xhtml" media-type="application/xhtml+xml"/>' for name, _ in chapters)
    spine = ''.join(f'<itemref idref="{name}"/>' for name in (order or [c[0] for c in chapters]))
    nav = '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
    if version.startswith('2'):
        nav = '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
    entries = {
        'mimetype': b'application/epub+zip',
        'META-INF/container.xml': b'<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="Book/package.opf" media-type="application/oebps-package+xml"/></rootfiles></container>',
        'Book/package.opf': f'<package xmlns="http://www.idpf.org/2007/opf" version="{version}" unique-identifier="uid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="uid">fixture-id</dc:identifier><dc:title>Fixture Book</dc:title><dc:language>en</dc:language><dc:creator>Fixture Author</dc:creator></metadata><manifest>{manifest}{nav}</manifest><spine toc="ncx">{spine}</spine></package>'.encode(),
        'Book/nav.xhtml': b'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Contents</title></head><body><nav epub:type="toc"><ol><li><a href="Text/one.xhtml">Start</a></li></ol></nav></body></html>',
    }
    if version.startswith('2'):
        entries.pop('Book/nav.xhtml')
        entries['Book/toc.ncx'] = b'<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/"><navMap><navPoint id="np"><content src="Text/one.xhtml"/></navPoint></navMap></ncx>'
    for name, body in chapters:
        entries[f'Book/Text/{name}.xhtml'] = f'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>{name}</title></head><body>{body}</body></html>'.encode()
    entries.update(replacements or {})
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in entries.items():
            if data is not None:
                archive.writestr(name, data, compress_type=zipfile.ZIP_STORED if name == 'mimetype' else zipfile.ZIP_DEFLATED)


class ToolsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='epub skill test ')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def run_tool(self, *args):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = tools.main(list(args))
        payload = json.loads(output.getvalue() or error.getvalue())
        return code, payload

    def test_mobile_long_cjk_no_regex_crash(self):
        text = '这是自己编写的测试句子，用于验证文字不会丢失。' * 40
        pieces = tools.split_paragraph(text, 120, 180)
        self.assertEqual(''.join(pieces), text)
        self.assertGreater(len(pieces), 1)
        self.assertTrue(all(len(p) <= 180 for p in pieces))

    def test_mobile_english_preserves_spaces(self):
        text = 'A synthetic sentence with several words. ' * 40
        pieces = tools.split_paragraph(text, 80, 120)
        self.assertEqual(''.join(pieces), text)
        self.assertTrue(all(len(p) <= 120 for p in pieces))

    def test_mobile_protects_multiblock_code_math_html(self):
        body = 'word ' * 100
        text = f'# Heading\n\n```python\n{body}\n\n{body}\n```\n\n$$\n{body}\n\n{body}\n$$\n\n<div>\n{body}\n\n{body}\n</div>\n'
        source, output = self.root/'clean.md', self.root/'mobile.md'
        source.write_text(text, encoding='utf-8')
        code, report = self.run_tool('mobile', '--input', str(source), '--output', str(output))
        self.assertEqual(code, 0)
        self.assertIn(f'```python\n{body}\n\n{body}\n```', output.read_text(encoding='utf-8'))
        self.assertIn(f'$$\n{body}\n\n{body}\n$$', output.read_text(encoding='utf-8'))
        self.assertIn(f'<div>\n{body}\n\n{body}\n</div>', output.read_text(encoding='utf-8'))
        self.assertEqual(source.read_text(encoding='utf-8'), text)

    def test_mobile_does_not_split_inline_markup(self):
        block = ('[linked words](image.png) **emphasis** $x+y$ ' * 30)
        self.assertTrue(tools.is_protected_markdown_block(block))

    def test_mobile_preserves_setext_title_and_indented_code(self):
        text = '长' * 220 + '\n===\n\n    first\n\n\n    second\n'
        source, output = self.root/'clean.md', self.root/'mobile.md'
        source.write_text(text, encoding='utf-8')
        code, _ = self.run_tool('mobile', '--input', str(source), '--output', str(output))
        self.assertEqual(code, 0)
        self.assertIn('长' * 220 + '\n===', output.read_text(encoding='utf-8'))
        self.assertIn('    first\n\n\n    second', output.read_text(encoding='utf-8'))

    def test_mobile_preserves_indented_raw_html(self):
        source, output = self.root/'clean.md', self.root/'mobile.md'
        text = '<pre>\n    first\n    second\n\n    third\n</pre>\n'
        source.write_text(text, encoding='utf-8')
        self.assertEqual(self.run_tool('mobile', '--input', str(source), '--output', str(output))[0], 0)
        self.assertEqual(output.read_text(encoding='utf-8'), text)

    def test_mobile_preserves_yaml_frontmatter(self):
        text = '---\ntitle: ' + 'word '*100 + '\n\nauthor: Someone\n---\n\nBody\n'
        source, output = self.root/'clean.md', self.root/'mobile.md'
        source.write_text(text, encoding='utf-8')
        code, _ = self.run_tool('mobile', '--input', str(source), '--output', str(output))
        self.assertEqual(code, 0)
        self.assertEqual(output.read_text(encoding='utf-8'), text)

    def test_mobile_long_unbreakable_word_is_reported(self):
        source, output = self.root/'clean.md', self.root/'mobile.md'
        source.write_text('a'*500)
        code, report = self.run_tool('mobile', '--input', str(source), '--output', str(output))
        self.assertEqual(code, 1)
        self.assertTrue(report['unresolved_blocks'])
        self.assertEqual(output.read_text(encoding='utf-8').strip(), 'a'*500)

    def test_mobile_rejects_input_output_alias_even_with_force(self):
        source = self.root/'clean.md'; source.write_text('original')
        code, report = self.run_tool('mobile', '--input', str(source), '--output', str(source), '--force')
        self.assertEqual(code, 2)
        self.assertEqual(source.read_text(encoding='utf-8'), 'original')

    def test_existing_output_requires_force(self):
        source, output = self.root/'clean.md', self.root/'mobile.md'
        source.write_text('new'); output.write_text('old')
        code, _ = self.run_tool('mobile', '--input', str(source), '--output', str(output))
        self.assertEqual(code, 2); self.assertEqual(output.read_text(encoding='utf-8'), 'old')

    def test_invalid_split_parameters(self):
        source = self.root/'clean.md'; source.write_text('text')
        code, _ = self.run_tool('mobile', '--input', str(source), '--output', str(self.root/'out.md'), '--target-min', '0')
        self.assertEqual(code, 2)

    def test_numeric_sorting(self):
        for name in ['10_ten.md', '002_two.md', '01_one.md', 'glossary.md']:
            (self.root/name).write_text(name)
        self.assertEqual([p.name for p in tools.numbered_markdown_files(self.root)], ['01_one.md','002_two.md','10_ten.md'])

    def test_duplicate_numbers_rejected(self):
        (self.root/'01_a.md').write_text('a'); (self.root/'001_b.md').write_text('b')
        with self.assertRaises(ValueError): tools.numbered_markdown_files(self.root)

    def test_merge_gap_and_empty_chapter_rejected(self):
        (self.root/'01_a.md').write_text('a'); (self.root/'03_c.md').write_text('c')
        code, _ = self.run_tool('merge', '--input', str(self.root), '--output', str(self.root/'clean.md'))
        self.assertEqual(code, 2)
        (self.root/'02_b.md').write_text('')
        code, _ = self.run_tool('merge', '--input', str(self.root), '--output', str(self.root/'clean.md'))
        self.assertEqual(code, 2)

    def test_large_chapter_gap_is_bounded_and_explicit(self):
        (self.root/'01_a.md').write_text('a', encoding='utf-8')
        (self.root/'999999999_b.md').write_text('b', encoding='utf-8')
        output = self.root/'clean.md'
        self.assertEqual(self.run_tool('merge', '--input', str(self.root), '--output', str(output))[0], 2)
        code, report = self.run_tool('merge', '--input', str(self.root), '--output', str(output), '--allow-gaps')
        self.assertEqual(code, 0)
        self.assertEqual(report['gaps'], ['2-999999998'])
        self.assertEqual(output.read_text(encoding='utf-8'), 'a\n\nb\n')

    def test_merge_preserves_real_separators_and_code_whitespace(self):
        body = '# Title\n\n---\n\nBody\n\n```\nfirst\n\n\nlast\n```\n'
        self.assertEqual(tools.strip_work_headers(body), body)
        header = '# Title\n\n原文标题：Source\n\n来源文件：01_source.md\n\n---\n\nBody\n\n---\n\nEnd\n'
        cleaned = tools.strip_work_headers(header)
        self.assertNotIn('来源文件', cleaned)
        self.assertIn('Body\n\n---\n\nEnd', cleaned)

    def test_merge_never_overwrites_input(self):
        source = self.root/'01_a.md'; source.write_text('# original')
        code, _ = self.run_tool('merge', '--input', str(self.root), '--output', str(source), '--force')
        self.assertEqual(code, 2); self.assertEqual(source.read_text(encoding='utf-8'), '# original')

    def test_valid_epub3_and_epub2(self):
        for version in ['3.0', '2.0']:
            path = self.root/(version+'.epub'); epub(path, version=version)
            code, report = self.run_tool('qc', '--epub', str(path))
            self.assertEqual(code, 0, report)

    def test_inspect_spine_order_not_zip_order(self):
        path = self.root/'test.epub'; epub(path, chapters=[('one','<p>One</p>'),('two','<p>Two</p>')], order=['two','one'])
        code, report = self.run_tool('inspect', '--epub', str(path))
        self.assertEqual(code, 0)
        self.assertEqual([i['idref'] for i in report['spine']], ['two','one'])
        self.assertEqual(len(report['sha256']), 64)
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(report['spine'][0]['sha256'], hashlib.sha256(archive.read('Book/Text/two.xhtml')).hexdigest())

    def test_corrupt_zip_and_xml_are_json_errors(self):
        path = self.root/'bad.epub'; path.write_bytes(b'not a zip')
        self.assertEqual(self.run_tool('qc', '--epub', str(path))[0], 1)
        epub(path, replacements={'META-INF/container.xml':b'<broken>'})
        self.assertEqual(self.run_tool('qc', '--epub', str(path))[0], 1)

    def test_mimetype_content_checked(self):
        path=self.root/'test.epub'; epub(path,replacements={'mimetype':b'wrong'})
        self.assertEqual(self.run_tool('qc','--epub',str(path))[0],1)

    def test_must_contain_is_requirement(self):
        path=self.root/'test.epub'; epub(path)
        code,report=self.run_tool('qc','--epub',str(path),'--must-contain','absent required text')
        self.assertEqual(code,1); self.assertIn('Missing required text', ' '.join(report['errors']))

    def test_url_encoded_resources_and_fragments(self):
        path=self.root/'test.epub'
        body='<p id="节一">Fixture.</p><a href="#%E8%8A%82%E4%B8%80">Jump</a><img src="../Images/test%20image.png?x=1"/>'
        epub(path,chapters=[('one',body)],replacements={'Book/Images/test image.png':b'fixture'})
        code,report=self.run_tool('qc','--epub',str(path))
        self.assertEqual(code,0,report)

    def test_broken_anchor_detected(self):
        path=self.root/'test.epub'; epub(path,chapters=[('one','<p>Text</p><a href="#missing">Jump</a>')])
        code,report=self.run_tool('qc','--epub',str(path))
        self.assertEqual(code,1); self.assertTrue(report['broken_links'])

    def test_qc_manifest_xhtml_without_extension(self):
        path=self.root/'test.epub'; epub(path)
        with zipfile.ZipFile(path) as archive:
            opf=archive.read('Book/package.opf').replace(b'Text/one.xhtml',b'Text/chapter')
        body=b'<html xmlns="http://www.w3.org/1999/xhtml"><body><img src="absent.png"/><a href="#missing">Jump</a></body></html>'
        epub(path,replacements={'Book/package.opf':opf,'Book/Text/chapter':body})
        code,report=self.run_tool('qc','--epub',str(path))
        self.assertEqual(code,1); self.assertTrue(report['broken_links']); self.assertTrue(report['broken_images'])

    def test_qc_compact_xml_work_headers_detected(self):
        path=self.root/'test.epub'
        epub(path,chapters=[('one','<h1>Chapter</h1><p>原文标题：Source</p><p>来源文件：one.xhtml</p><p>Text</p>')])
        code,report=self.run_tool('qc','--epub',str(path))
        self.assertEqual(code,1); self.assertEqual(len(report['forbidden_hits']),2)

    def test_compare_keeps_body_outside_nav_element(self):
        left,right=self.root/'a.epub',self.root/'b.epub'; epub(left)
        with zipfile.ZipFile(left) as archive:
            opf=archive.read('Book/package.opf').replace(b'<spine toc="ncx">',b'<spine toc="ncx"><itemref idref="nav"/>')
            nav=archive.read('Book/nav.xhtml')
        epub(left,replacements={'Book/package.opf':opf,'Book/nav.xhtml':nav.replace(b'</body>',b'<p>Important preface.</p></body>')})
        epub(right,replacements={'Book/package.opf':opf,'Book/nav.xhtml':nav})
        code,report=self.run_tool('compare','--left',str(left),'--right',str(right))
        self.assertEqual(code,1); self.assertFalse(report['equal_ignoring_whitespace'])

    def test_duplicate_ids_detected(self):
        path=self.root/'test.epub'; epub(path,chapters=[('one','<p id="same">A</p><p id="same">B</p>')])
        self.assertEqual(self.run_tool('qc','--epub',str(path))[0],1)

    def test_source_text_may_mention_glossary(self):
        path=self.root/'test.epub'; epub(path,chapters=[('one','<p>本书介绍译名表与校对报告的历史。</p>')])
        self.assertEqual(self.run_tool('qc','--epub',str(path))[0],0)

    def test_unsafe_archive_path_and_entities_rejected(self):
        path=self.root/'test.epub'; epub(path,replacements={'../escape':b'bad'})
        self.assertEqual(self.run_tool('inspect','--epub',str(path))[0],1)
        epub(path,replacements={'META-INF/container.xml':b'<!DOCTYPE a [<!ENTITY x "bomb">]><a>&x;</a>'})
        self.assertEqual(self.run_tool('inspect','--epub',str(path))[0],1)

    def test_report_cannot_replace_epub(self):
        path=self.root/'test.epub'; epub(path); before=path.read_bytes()
        code,_=self.run_tool('qc','--epub',str(path),'--json',str(path),'--force')
        self.assertEqual(code,2); self.assertEqual(path.read_bytes(),before)

    def test_comparison_uses_spine_and_excludes_head_nav(self):
        left,right=self.root/'a.epub',self.root/'b.epub'
        epub(left,chapters=[('one','<p>A B C</p>')]);epub(right,chapters=[('one','<p>A</p><p>B C</p>')])
        self.assertEqual(self.run_tool('compare','--left',str(left),'--right',str(right))[0],0)
        epub(right,chapters=[('one','<p>A B DIFFERENT</p>')])
        self.assertEqual(self.run_tool('compare','--left',str(left),'--right',str(right))[0],1)

    def test_empty_text_not_equivalent(self):
        left,right=self.root/'a.epub',self.root/'b.epub'
        epub(left,chapters=[('one','<p/>')]);epub(right,chapters=[('one','<p/>')])
        self.assertEqual(self.run_tool('compare','--left',str(left),'--right',str(right))[0],1)

    @unittest.skipUnless(shutil.which('pandoc'), 'Pandoc optional integration')
    def test_real_pandoc_desktop_mobile_roundtrip(self):
        chapters=self.root/'chapters'; chapters.mkdir()
        text='# Fixture Chapter\n\n' + '这是原创测试句子，只用于验证电子书转换。'*40 + '\n'
        (chapters/'01_fixture.md').write_text(text,encoding='utf-8')
        clean,mobile=self.root/'clean.md',self.root/'mobile.md'
        self.assertEqual(self.run_tool('merge','--input',str(chapters),'--output',str(clean))[0],0)
        self.assertEqual(self.run_tool('mobile','--input',str(clean),'--output',str(mobile))[0],0)
        outputs=[]
        for source in [clean,mobile]:
            output=source.with_suffix('.epub');outputs.append(output)
            subprocess.run(['pandoc',str(source),'-o',str(output),'--metadata','title=Fixture','--metadata','lang=zh-CN'],check=True,capture_output=True)
            code,report=self.run_tool('qc','--epub',str(output),'--must-contain','原创测试句子')
            self.assertEqual(code,0,report)
        self.assertEqual(self.run_tool('compare','--left',str(outputs[0]),'--right',str(outputs[1]))[0],0)
        self.assertEqual((chapters/'01_fixture.md').read_text(encoding='utf-8'),text)

    def test_cli_unicode_paths_with_legacy_console_encoding(self):
        chapters = self.root/'章节'; chapters.mkdir()
        (chapters/'01_第一章.md').write_text('# 第一章\n\n正文。', encoding='utf-8')
        env = dict(os.environ, PYTHONIOENCODING='cp1252')
        import sys
        cli = [sys.executable, str(ROOT/'scripts/epub_project_tools.py')]
        result = subprocess.run(cli + ['merge', '--input', str(chapters), '--output', str(self.root/'合并.md')], env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['chapters'], ['01_第一章.md'])
        path = self.root/'电子书.epub'; epub(path)
        report = self.root/'报告.json'
        result = subprocess.run(cli + ['qc', '--epub', str(path), '--json', str(report)], env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), json.loads(report.read_text(encoding='utf-8')))
        self.assertIn('电子书', report.read_text(encoding='utf-8'))


if __name__=='__main__':
    unittest.main()
