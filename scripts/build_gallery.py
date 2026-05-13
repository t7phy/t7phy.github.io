from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from html import escape
from pathlib import Path

import imageio.v3 as iio
from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "gallery.toml"
TEMPLATE_PATH = ROOT / "templates" / "gallery.base.html"
VIEW_TEMPLATE_PATH = ROOT / "templates" / "gallery.view.base.html"
OUTPUT_PATH = ROOT / "gallery.html"
VIEW_OUTPUT_PATH = ROOT / "gallery-view.html"

POSTS_DIR = ROOT / "assets" / "gallery" / "posts"
GENERATED_DIR = ROOT / "assets" / "gallery" / "generated"
THUMBS_DIR = GENERATED_DIR / "thumbs"
POSTERS_DIR = GENERATED_DIR / "posters"

THUMB_SIZE = 960
POSTER_SIZE = 1600
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".m4v"}


@dataclass(frozen=True)
class MediaItem:
    type: str
    src: str
    alt: str
    poster: str | None = None
    autoplay: bool = False


@dataclass(frozen=True)
class GalleryPost:
    slug: str
    caption: str
    date: str | None
    thumb: str
    items: list[MediaItem]


def _req(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing or invalid '{label}'.")
    return value.strip()


def _detect_type(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    raise ValueError(f"Unsupported media extension: {name}")


def _center_crop(image: Image.Image, size: int) -> Image.Image:
    w, h = image.size
    side = min(w, h)
    x = (w - side) // 2
    y = (h - side) // 2
    cropped = image.crop((x, y, x + side, y + side))
    return cropped.resize((size, size), Image.Resampling.LANCZOS)


def _contain_square(image: Image.Image, size: int) -> Image.Image:
    canvas = Image.new("RGB", (size, size), color=(30, 30, 30))
    src = image.copy()
    src.thumbnail((size, size), Image.Resampling.LANCZOS)
    x = (size - src.width) // 2
    y = (size - src.height) // 2
    canvas.paste(src, (x, y))
    return canvas


def _first_video_frame(path: Path) -> Image.Image:
    frame = iio.imread(path, index=0)
    return Image.fromarray(frame).convert("RGB")


def _load_image(path: Path, media_type: str) -> Image.Image:
    if media_type == "image":
        return Image.open(path).convert("RGB")
    return _first_video_frame(path)


def _build_thumb(source: Path, media_type: str, mode: str, dest: Path) -> None:
    image = _load_image(source, media_type)
    thumb = _center_crop(image, THUMB_SIZE) if mode == "crop" else _contain_square(image, THUMB_SIZE)
    thumb.save(dest, format="JPEG", quality=88, optimize=True)


def _build_poster(source: Path, dest: Path) -> None:
    image = _first_video_frame(source)
    image.thumbnail((POSTER_SIZE, POSTER_SIZE), Image.Resampling.LANCZOS)
    image.save(dest, format="JPEG", quality=90, optimize=True)


def _to_web(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _render_cards(posts: list[GalleryPost]) -> str:
    cards: list[str] = []
    for index, post in enumerate(posts):
        multi_icon = '<span class="gallery-card-multi" aria-hidden="true"></span>' if len(post.items) > 1 else ""
        cards.append(
            (
                f'<article class="gallery-card" data-post-index="{index}">'
                f"{multi_icon}"
                f'<img src="{escape(post.thumb)}" alt="Gallery post {index + 1}" loading="lazy" decoding="async" />'
                "</article>"
            )
        )
    return "\n        ".join(cards)


def build() -> None:
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    POSTERS_DIR.mkdir(parents=True, exist_ok=True)

    with DATA_PATH.open("rb") as f:
        data = tomllib.load(f)

    posts_raw = data.get("posts")
    if not isinstance(posts_raw, list) or not posts_raw:
        raise ValueError("data/gallery.toml must contain a non-empty 'posts' array.")

    keep_thumbs: set[Path] = set()
    keep_posters: set[Path] = set()
    posts: list[GalleryPost] = []

    for index, raw in enumerate(reversed(posts_raw), start=1):
        slug = _req(raw.get("slug"), f"posts[{index}].slug")
        caption = _req(raw.get("caption"), f"posts[{index}].caption")
        date_raw = raw.get("date")
        date_value = date_raw.strip() if isinstance(date_raw, str) and date_raw.strip() else None
        thumb_item = _req(raw.get("thumb_item"), f"posts[{index}].thumb_item")
        thumb_mode = _req(raw.get("thumb_mode"), f"posts[{index}].thumb_mode").lower()
        if thumb_mode not in {"crop", "contain"}:
            raise ValueError(f"posts[{index}].thumb_mode must be 'crop' or 'contain'.")

        items_raw = raw.get("items")
        if not isinstance(items_raw, list) or not items_raw:
            raise ValueError(f"posts[{index}] must include at least one items entry.")

        post_dir = POSTS_DIR / slug
        if not post_dir.exists():
            raise ValueError(f"Missing post directory: {post_dir}")

        media_items: list[MediaItem] = []
        thumb_source: Path | None = None
        thumb_source_type = "image"

        for item_idx, item_raw in enumerate(items_raw, start=1):
            file_name = _req(item_raw.get("file"), f"posts[{index}].items[{item_idx}].file")
            media_path = post_dir / file_name
            if not media_path.exists():
                raise ValueError(f"Missing media file: {media_path}")
            media_type = _detect_type(file_name)
            alt = item_raw.get("alt")
            alt_text = alt.strip() if isinstance(alt, str) else ""

            poster_web = None
            if media_type == "video":
                poster_path = POSTERS_DIR / f"{slug}__{item_idx}.jpg"
                _build_poster(media_path, poster_path)
                keep_posters.add(poster_path)
                poster_web = _to_web(poster_path)
                play_mode = item_raw.get("play")
                autoplay = isinstance(play_mode, str) and play_mode.strip().lower() == "play"
            else:
                autoplay = False

            media_items.append(
                MediaItem(
                    type=media_type,
                    src=_to_web(media_path),
                    alt=alt_text,
                    poster=poster_web,
                    autoplay=autoplay,
                )
            )

            if file_name == thumb_item:
                thumb_source = media_path
                thumb_source_type = media_type

        if thumb_source is None:
            raise ValueError(f"posts[{index}] thumb_item '{thumb_item}' was not found in items.")

        thumb_path = THUMBS_DIR / f"{slug}.jpg"
        _build_thumb(thumb_source, thumb_source_type, thumb_mode, thumb_path)
        keep_thumbs.add(thumb_path)

        posts.append(
            GalleryPost(
                slug=slug,
                caption=caption,
                date=date_value,
                thumb=_to_web(thumb_path),
                items=media_items,
            )
        )

    for stale in THUMBS_DIR.glob("*.jpg"):
        if stale not in keep_thumbs:
            stale.unlink()
    for stale in POSTERS_DIR.glob("*.jpg"):
        if stale not in keep_posters:
            stale.unlink()

    payload = [
        {
            "slug": post.slug,
            "caption": post.caption,
            "date": post.date,
            "thumb": post.thumb,
            "items": [
                {"type": item.type, "src": item.src, "alt": item.alt, "poster": item.poster}
                | {"autoplay": item.autoplay}
                for item in post.items
            ],
        }
        for post in posts
    ]

    json_payload = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = html.replace("{{GALLERY_CARDS}}", _render_cards(posts))
    html = html.replace("{{GALLERY_DATA}}", json_payload)
    OUTPUT_PATH.write_text(html, encoding="utf-8")

    view_html = VIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
    view_html = view_html.replace("{{GALLERY_DATA}}", json_payload)
    VIEW_OUTPUT_PATH.write_text(view_html, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Wrote {VIEW_OUTPUT_PATH}")


if __name__ == "__main__":
    build()
