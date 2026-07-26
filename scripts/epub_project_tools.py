#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reusable helpers for two-pass EPUB translation projects."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import zipfile
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


WORK_HEADER_PREFIXES = ("原文标题：", "来源文件：", "来源 EPUB：")
SKIP_FILENAMES = {"译名表.md", "校对报告.md"}
TEXT_EXTENSIONS = {".xhtml", ".html", ".htm"}
XML_NS = {
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def numbered_markdown_files(folder: Path) -> list[Path]:
    files = []
    for path in folder.glob("*.md"):
        if path.name in SKIP_FILENAMES:
            continue
        if re.match(r"^\d{2,3}_", path.name):
            files.append(path)
    return sorted(files, key=lambda p: p.name)


def strip_work_headers(markdown: str) -> str:
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    skip_next_blank = False
    in_header_zone = True
    for line in lines:
        stripped = line.strip()
        if in_header_zone and any(stripped.startswith(prefix) for prefix in WORK_HEADER_PREFIXES):
            skip_next_blank = True
            continue
        if in_header_zone and stripped == "---":
            skip_next_blank = True
            continue
        if skip_next_blank and stripped == "":
            continue
        skip_next_blank = False
        if stripped and not stripped.startswith("#"):
            in_header_zone = False
        out.append(line)
    text = "\n".join(out).strip()
    return re.sub(r"\n{3,}", "\n\n", text) + "\n"


def merge_command(args: argparse.Namespace) -> int:
    source = Path(args.input)
    output = Path(args.output)
    files = numbered_markdown_files(source)
    if args.skip_first and files:
        files = files[1:]
    if not files:
        raise SystemExit(f"No numbered Markdown files found in {source}")
    chunks = [strip_work_headers(read_text(path)) for path in files]
    write_text(output, "\n\n".join(chunk.strip() for chunk in chunks if chunk.strip()) + "\n")
    print(json.dumps({"files": len(files), "output": str(output)}, ensure_ascii=False, indent=2))
    return 0


def is_protected_markdown_block(block: str) -> bool:
    stripped = block.strip()
    if not stripped:
        return True
    protected_prefixes = ("#", "!", "|", ">", "- ", "* ", "+ ", "```", "<")
    if stripped.startswith(protected_prefixes):
        return True
    if re.match(r"^\d+[.)]\s", stripped):
        return True
    if re.search(r"https?://|ISBN|^\s*[\w.-]+@[\w.-]+", stripped, re.I):
        return True
    return False


def split_paragraph(text: str, target_min: int, target_max: int) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if len(text) <= target_max:
        return [text]
    sentences = re.split(r"(?<=[。！？；：.!?;:][”’」』》）】]*)(?=\s*[^”’」』》）】])", text)
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = sentence if not current else current + sentence
        if len(candidate) <= target_max or len(current) < target_min:
            current = candidate
        else:
            pieces.append(current)
            current = sentence
    if current:
        pieces.append(current)
    refined: list[str] = []
    for piece in pieces:
        if len(piece) <= 300:
            refined.append(piece)
            continue
        subparts = re.split(r"(?<=[，、,])(?=\S)", piece)
        current = ""
        for part in subparts:
            candidate = part if not current else current + part
            if len(candidate) <= target_max or len(current) < target_min:
                current = candidate
            else:
                refined.append(current)
                current = part
        if current:
            refined.append(current)
    return refined


def mobile_command(args: argparse.Namespace) -> int:
    source = Path(args.input)
    output = Path(args.output)
    text = read_text(source).replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n{2,}", text)
    out: list[str] = []
    split_blocks = 0
    generated_pieces = 0
    for block in blocks:
        if is_protected_markdown_block(block) or len(block.strip()) <= args.threshold:
            out.append(block.strip())
            continue
        pieces = split_paragraph(block, args.target_min, args.target_max)
        split_blocks += 1
        generated_pieces += len(pieces)
        out.extend(pieces)
    write_text(output, "\n\n".join(block for block in out if block) + "\n")
    print(json.dumps({
        "input": str(source),
        "output": str(output),
        "split_blocks": split_blocks,
        "generated_pieces": generated_pieces,
    }, ensure_ascii=False, indent=2))
    return 0


def parse_xml_from_zip(zf: zipfile.ZipFile, name: str) -> ET.Element:
    return ET.fromstring(zf.read(name))


def normalize_href(base: str, href: str) -> str:
    href = href.split("#", 1)[0]
    return posixpath.normpath(posixpath.join(posixpath.dirname(base), href))


def xhtml_files(zf: zipfile.ZipFile) -> list[str]:
    return [name for name in zf.namelist() if Path(name).suffix.lower() in TEXT_EXTENSIONS]


def text_from_element(element: ET.Element) -> str:
    parts: list[str] = []
    if element.text:
        parts.append(element.text)
    for child in element:
        parts.append(text_from_element(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def collect_ids(element: ET.Element) -> set[str]:
    ids = set()
    for node in element.iter():
        value = node.attrib.get("id")
        if value:
            ids.add(value)
    return ids


def qc_command(args: argparse.Namespace) -> int:
    epub = Path(args.epub)
    report: dict[str, object] = {
        "epub": str(epub),
        "exists": epub.exists(),
        "size": epub.stat().st_size if epub.exists() else 0,
        "errors": [],
        "warnings": [],
    }
    errors: list[str] = report["errors"]  # type: ignore[assignment]
    warnings: list[str] = report["warnings"]  # type: ignore[assignment]
    if not epub.exists():
        errors.append("EPUB file does not exist")
        return write_report(args, report, 1)

    with zipfile.ZipFile(epub) as zf:
        infos = zf.infolist()
        names = zf.namelist()
        report["zip_entries"] = len(names)
        if not infos or infos[0].filename != "mimetype":
            errors.append("mimetype is not the first ZIP entry")
        elif infos[0].compress_type != zipfile.ZIP_STORED:
            errors.append("mimetype is compressed")
        if "META-INF/container.xml" not in names:
            errors.append("META-INF/container.xml missing")
            return write_report(args, report, 1)

        container = parse_xml_from_zip(zf, "META-INF/container.xml")
        rootfile = container.find(".//container:rootfile", XML_NS)
        if rootfile is None:
            errors.append("container.xml has no rootfile")
            return write_report(args, report, 1)
        opf_path = rootfile.attrib.get("full-path", "")
        report["opf_path"] = opf_path
        if opf_path not in names:
            errors.append("OPF file missing")
            return write_report(args, report, 1)

        opf = parse_xml_from_zip(zf, opf_path)
        report["metadata"] = {
            "title": opf.findtext(".//dc:title", default="", namespaces=XML_NS),
            "creator": opf.findtext(".//dc:creator", default="", namespaces=XML_NS),
            "language": opf.findtext(".//dc:language", default="", namespaces=XML_NS),
        }

        image_refs: list[str] = []
        broken_images: list[str] = []
        broken_links: list[str] = []
        forbidden_hits: list[str] = []
        id_map: dict[str, set[str]] = {}
        body_text_parts: list[str] = []

        for xhtml in xhtml_files(zf):
            try:
                root = parse_xml_from_zip(zf, xhtml)
            except ET.ParseError as exc:
                errors.append(f"XHTML parse error: {xhtml}: {exc}")
                continue
            id_map[xhtml] = collect_ids(root)
            body_text_parts.append(text_from_element(root))
            for node in root.iter():
                tag = node.tag.rsplit("}", 1)[-1]
                if tag == "img":
                    src = node.attrib.get("src")
                    if src:
                        target = normalize_href(xhtml, src)
                        image_refs.append(target)
                        if target not in names:
                            broken_images.append(f"{xhtml} -> {src}")
                if tag == "a":
                    href = node.attrib.get("href")
                    if href and not re.match(r"^[a-z]+:", href, re.I):
                        file_part, _, anchor = href.partition("#")
                        target_file = normalize_href(xhtml, file_part) if file_part else xhtml
                        if target_file not in names:
                            broken_links.append(f"{xhtml} -> {href}")
                        elif anchor and anchor not in id_map.get(target_file, set()):
                            try:
                                target_root = parse_xml_from_zip(zf, target_file)
                                id_map[target_file] = collect_ids(target_root)
                            except ET.ParseError:
                                pass
                            if anchor not in id_map.get(target_file, set()):
                                broken_links.append(f"{xhtml} -> {href}")

        text = "\n".join(body_text_parts)
        for marker in ("原文标题：", "来源文件：", "来源 EPUB：", "校对报告", "译名表"):
            if marker in text:
                forbidden_hits.append(marker)

        report["xhtml_files"] = len(xhtml_files(zf))
        report["image_refs"] = len(image_refs)
        report["broken_images"] = broken_images
        report["broken_links"] = broken_links
        report["forbidden_hits"] = forbidden_hits
        if broken_images:
            errors.append(f"Broken image refs: {len(broken_images)}")
        if broken_links:
            errors.append(f"Broken internal links: {len(broken_links)}")
        if forbidden_hits:
            errors.append(f"Forbidden work markers present: {forbidden_hits}")
        for needle in args.must_contain or []:
            if needle not in text:
                warnings.append(f"Missing expected text: {needle}")

    return write_report(args, report, 1 if errors else 0)


def write_report(args: argparse.Namespace, report: dict[str, object], status: int) -> int:
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if getattr(args, "json", None):
        write_text(Path(args.json), text + "\n")
    print(text)
    return status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    merge = sub.add_parser("merge", help="Merge numbered translated Markdown files")
    merge.add_argument("--input", required=True, help="Translation folder")
    merge.add_argument("--output", required=True, help="Clean Markdown output")
    merge.add_argument("--skip-first", action="store_true", help="Skip first numbered file, usually cover")
    merge.set_defaults(func=merge_command)

    mobile = sub.add_parser("mobile", help="Split long ordinary paragraphs for mobile reading")
    mobile.add_argument("--input", required=True, help="Clean Markdown input")
    mobile.add_argument("--output", required=True, help="Mobile Markdown output")
    mobile.add_argument("--threshold", type=int, default=180)
    mobile.add_argument("--target-min", type=int, default=120)
    mobile.add_argument("--target-max", type=int, default=180)
    mobile.set_defaults(func=mobile_command)

    qc = sub.add_parser("qc", help="Validate common EPUB package and content issues")
    qc.add_argument("--epub", required=True, help="EPUB file")
    qc.add_argument("--json", help="Optional JSON report path")
    qc.add_argument("--must-contain", action="append", help="Expected text marker in EPUB body")
    qc.set_defaults(func=qc_command)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
