from __future__ import annotations

import tomllib
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Callable

try:
    from latex2mathml import converter as latex2mathml_converter
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "Missing dependency 'latex2mathml'. Activate the project venv and run: "
        ".venv\\Scripts\\python.exe -m pip install latex2mathml"
    ) from exc


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "research.html"
BASE_TEMPLATE_PATH = ROOT / "templates" / "research.base.html"


@dataclass(frozen=True)
class SectionConfig:
    placeholder: str
    template_path: Path
    data_path: Path
    renderer: Callable[[dict, str], str]


def _require_non_empty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Invalid or missing '{label}'.")
    return value.strip()


def _escape_attr(text: str) -> str:
    return escape(text, quote=True)


def _split_inline_latex(text: str) -> list[tuple[bool, str]]:
    parts: list[tuple[bool, str]] = []
    buffer: list[str] = []
    in_math = False
    i = 0

    while i < len(text):
        char = text[i]
        if char == "\\" and i + 1 < len(text) and text[i + 1] == "$":
            buffer.append("$")
            i += 2
            continue
        if char == "$":
            parts.append((in_math, "".join(buffer)))
            buffer = []
            in_math = not in_math
            i += 1
            continue
        buffer.append(char)
        i += 1

    if in_math:
        raise ValueError("Unclosed inline LaTeX delimiter '$' in title text.")

    parts.append((in_math, "".join(buffer)))
    return parts


def _render_title_with_latex(title_text: str, label: str) -> str:
    segments = _split_inline_latex(title_text)
    rendered_parts: list[str] = []

    for is_math, chunk in segments:
        if not chunk:
            continue
        if not is_math:
            rendered_parts.append(escape(chunk))
            continue
        try:
            mathml = latex2mathml_converter.convert(chunk)
        except Exception as exc:
            raise ValueError(f"{label}: invalid LaTeX fragment '${chunk}$'") from exc
        rendered_parts.append(f'<span class="inline-math">{mathml}</span>')

    return "".join(rendered_parts)


def _render_publication_entry(entry: dict, index: int) -> str:
    name_text = _require_non_empty_string(entry.get("name_text"), f"publications[{index}].name_text")
    name_link = _require_non_empty_string(entry.get("name_link"), f"publications[{index}].name_link")
    identifier_text = _require_non_empty_string(
        entry.get("identifier_text"), f"publications[{index}].identifier_text"
    )
    identifier_link = _require_non_empty_string(
        entry.get("identifier_link"), f"publications[{index}].identifier_link"
    )
    bibtex = _require_non_empty_string(entry.get("bibtex"), f"publications[{index}].bibtex")
    bibtex_attr = _escape_attr(bibtex).replace("\n", "&#10;")
    name_html = _render_title_with_latex(name_text, f"publications[{index}].name_text")

    meta_parts: list[str] = [
        (
            f'<a class="publication-identifier" href="{_escape_attr(identifier_link)}" '
            f'target="_blank" rel="noopener noreferrer">{escape(identifier_text)}</a>'
        )
    ]

    arxiv = entry.get("arxiv")
    if isinstance(arxiv, str) and arxiv.strip():
        arxiv_id = arxiv.strip()
        meta_parts.append(
            (
                '<a class="publication-link" '
                f'href="https://arxiv.org/abs/{_escape_attr(arxiv_id)}" '
                f'target="_blank" rel="noopener noreferrer">arXiv:{escape(arxiv_id)}</a>'
            )
        )

    doi = entry.get("doi")
    if isinstance(doi, str) and doi.strip():
        doi_link = doi.strip()
        meta_parts.append(
            (
                f'<a class="publication-link" href="{_escape_attr(doi_link)}" '
                'target="_blank" rel="noopener noreferrer">DOI</a>'
            )
        )

    joined_meta: list[str] = []
    for idx, part in enumerate(meta_parts):
        if idx > 0:
            joined_meta.append('<span class="publication-sep">|</span>')
        joined_meta.append(part)

    return (
        "    <li>\n"
        '      <div class="publication-top">\n'
        f'        <a class="publication-name" href="{_escape_attr(name_link)}" '
        f'target="_blank" rel="noopener noreferrer">{name_html}</a>\n'
        f'        <button class="cite-button" type="button" '
        f'data-bibtex="{bibtex_attr}">cite</button>\n'
        "      </div>\n"
        f'      <div class="publication-meta">{" ".join(joined_meta)}</div>\n'
        "    </li>"
    )


def _render_preprint_entry(entry: dict, index: int) -> str:
    name_text = _require_non_empty_string(entry.get("name_text"), f"preprints[{index}].name_text")
    name_link = _require_non_empty_string(entry.get("name_link"), f"preprints[{index}].name_link")
    arxiv_id = _require_non_empty_string(entry.get("arxiv"), f"preprints[{index}].arxiv")
    bibtex = _require_non_empty_string(entry.get("bibtex"), f"preprints[{index}].bibtex")

    bibtex_attr = _escape_attr(bibtex).replace("\n", "&#10;")
    name_html = _render_title_with_latex(name_text, f"preprints[{index}].name_text")
    arxiv_link = (
        '<a class="publication-link" '
        f'href="https://arxiv.org/abs/{_escape_attr(arxiv_id)}" '
        f'target="_blank" rel="noopener noreferrer">arXiv:{escape(arxiv_id)}</a>'
    )

    return (
        "    <li>\n"
        '      <div class="publication-top">\n'
        f'        <a class="publication-name" href="{_escape_attr(name_link)}" '
        f'target="_blank" rel="noopener noreferrer">{name_html}</a>\n'
        f'        <button class="cite-button" type="button" '
        f'data-bibtex="{bibtex_attr}">cite</button>\n'
        "      </div>\n"
        f'      <div class="publication-meta">{arxiv_link}</div>\n'
        "    </li>"
    )


def _render_entries_section(
    data: dict,
    template_text: str,
    list_key: str,
    start_key: str,
    items_key: str,
    data_file: str,
    entry_renderer: Callable[[dict, int], str],
) -> str:
    entries = data.get(list_key)
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{data_file} must define a non-empty '{list_key}' array.")

    items = [
        entry_renderer(entry, index)
        for index, entry in enumerate(reversed(entries), start=1)
    ]

    return (
        template_text.replace(start_key, str(len(entries)))
        .replace(items_key, "\n".join(items))
    )


def render_publications_section(data: dict, template_text: str) -> str:
    return _render_entries_section(
        data=data,
        template_text=template_text,
        list_key="publications",
        start_key="{{PUBLICATIONS_START}}",
        items_key="{{PUBLICATIONS_ITEMS}}",
        data_file="data/publications.toml",
        entry_renderer=_render_publication_entry,
    )


def render_preprints_section(data: dict, template_text: str) -> str:
    preprints = data.get("preprints")
    if preprints is None:
        return ""
    if not isinstance(preprints, list):
        raise ValueError("data/preprints.toml field 'preprints' must be an array when present.")
    if len(preprints) == 0:
        return ""

    return _render_entries_section(
        data=data,
        template_text=template_text,
        list_key="preprints",
        start_key="{{PREPRINTS_START}}",
        items_key="{{PREPRINTS_ITEMS}}",
        data_file="data/preprints.toml",
        entry_renderer=_render_preprint_entry,
    )


def render_proceedings_section(data: dict, template_text: str) -> str:
    return _render_entries_section(
        data=data,
        template_text=template_text,
        list_key="proceedings",
        start_key="{{PROCEEDINGS_START}}",
        items_key="{{PROCEEDINGS_ITEMS}}",
        data_file="data/proceedings.toml",
        entry_renderer=_render_publication_entry,
    )


SECTIONS = [
    SectionConfig(
        placeholder="{{PREPRINTS_SECTION}}",
        template_path=ROOT / "templates" / "preprints.template.html",
        data_path=ROOT / "data" / "preprints.toml",
        renderer=render_preprints_section,
    ),
    SectionConfig(
        placeholder="{{PUBLICATIONS_SECTION}}",
        template_path=ROOT / "templates" / "publications.template.html",
        data_path=ROOT / "data" / "publications.toml",
        renderer=render_publications_section,
    ),
    SectionConfig(
        placeholder="{{PROCEEDINGS_SECTION}}",
        template_path=ROOT / "templates" / "proceedings.template.html",
        data_path=ROOT / "data" / "proceedings.toml",
        renderer=render_proceedings_section,
    ),
]


def build() -> None:
    page_html = BASE_TEMPLATE_PATH.read_text(encoding="utf-8")

    for section in SECTIONS:
        if section.placeholder not in page_html:
            raise ValueError(
                f"Placeholder '{section.placeholder}' not found in {BASE_TEMPLATE_PATH.name}."
            )
        section_template = section.template_path.read_text(encoding="utf-8")
        with section.data_path.open("rb") as f:
            section_data = tomllib.load(f)
        rendered = section.renderer(section_data, section_template)
        page_html = page_html.replace(section.placeholder, rendered)

    OUTPUT_PATH.write_text(page_html, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    build()
