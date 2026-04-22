from __future__ import annotations

import tomllib
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Callable


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
        f'target="_blank" rel="noopener noreferrer">{escape(name_text)}</a>\n'
        f'        <button class="cite-button" type="button" data-title="{_escape_attr(name_text)}" '
        f'data-bibtex="{bibtex_attr}">cite</button>\n'
        "      </div>\n"
        f'      <div class="publication-meta">{" ".join(joined_meta)}</div>\n'
        "    </li>"
    )


def render_publications_section(data: dict, template_text: str) -> str:
    publications = data.get("publications")
    if not isinstance(publications, list) or not publications:
        raise ValueError("data/publications.toml must define a non-empty 'publications' array.")

    items = [
        _render_publication_entry(entry, index)
        for index, entry in enumerate(reversed(publications), start=1)
    ]

    return (
        template_text.replace("{{PUBLICATIONS_START}}", str(len(publications)))
        .replace("{{PUBLICATIONS_ITEMS}}", "\n".join(items))
    )


SECTIONS = [
    SectionConfig(
        placeholder="{{PUBLICATIONS_SECTION}}",
        template_path=ROOT / "templates" / "publications.template.html",
        data_path=ROOT / "data" / "publications.toml",
        renderer=render_publications_section,
    )
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
