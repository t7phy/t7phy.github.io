from __future__ import annotations

import re
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE_PATH = ROOT / "data" / "cv.tex"
TEMPLATE_PATH = ROOT / "templates" / "cv.base.html"
OUTPUT_PATH = ROOT / "cv.html"


def _strip_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", text)


def _extract_document_body(text: str) -> str:
    match = re.search(r"\\begin\{document\}(.*)\\end\{document\}", text, flags=re.S)
    return match.group(1) if match else text


def _apply_inline_latex(text: str) -> str:
    text = escape(text)
    text = re.sub(r"\\textbf\{([^{}]*)\}", r"<strong>\1</strong>", text)
    text = re.sub(r"\\emph\{([^{}]*)\}", r"<em>\1</em>", text)
    text = re.sub(r"\\href\{([^{}]+)\}\{([^{}]*)\}", r'<a href="\1" target="_blank" rel="noopener noreferrer">\2</a>', text)
    text = re.sub(r"\\url\{([^{}]+)\}", r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>', text)
    text = text.replace(r"\\", "<br />")
    return text


def _convert_blocks(body: str) -> str:
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    out: list[str] = []
    in_ul = False
    in_ol = False

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    for raw in lines:
        if raw == r"\begin{itemize}":
            close_lists()
            out.append("<ul>")
            in_ul = True
            continue
        if raw == r"\end{itemize}":
            if in_ul:
                out.append("</ul>")
                in_ul = False
            continue
        if raw == r"\begin{enumerate}":
            close_lists()
            out.append("<ol>")
            in_ol = True
            continue
        if raw == r"\end{enumerate}":
            if in_ol:
                out.append("</ol>")
                in_ol = False
            continue
        if raw.startswith(r"\section{") and raw.endswith("}"):
            close_lists()
            out.append(f"<h2>{_apply_inline_latex(raw[9:-1])}</h2>")
            continue
        if raw.startswith(r"\subsection{") and raw.endswith("}"):
            close_lists()
            out.append(f"<h3>{_apply_inline_latex(raw[12:-1])}</h3>")
            continue
        if raw.startswith(r"\item"):
            text = raw[5:].strip()
            out.append(f"<li>{_apply_inline_latex(text)}</li>")
            continue
        close_lists()
        out.append(f"<p>{_apply_inline_latex(raw)}</p>")

    close_lists()
    return "\n".join(out)


def build() -> None:
    tex = SOURCE_PATH.read_text(encoding="utf-8")
    tex = _strip_comments(tex)
    body = _extract_document_body(tex)
    rendered = _convert_blocks(body)
    page = TEMPLATE_PATH.read_text(encoding="utf-8").replace("{{CV_CONTENT}}", rendered)
    OUTPUT_PATH.write_text(page, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    build()
