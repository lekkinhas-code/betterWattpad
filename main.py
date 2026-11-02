import re
import time
from pathlib import Path
from urllib.parse import urlparse

from chapter_export import (
    chapter_to_markdown,
    chapter_to_pdf,
    clean_html,
    count_characters,
    story_to_markdown,
    story_to_pdf,
)
from wattpad_api import get_chapter_html, get_story, get_story_id_for_part

DELAY_BETWEEN_CHAPTERS_SECONDS = 1
EXPORTS_DIR = Path(__file__).parent / "exports"
EXPORTERS = {"pdf": chapter_to_pdf, "md": chapter_to_markdown}
STORY_EXPORTERS = {"pdf": story_to_pdf, "md": story_to_markdown}


def _safe_filename(name):
    """Remove the characters Windows doesn't allow in file and folder names."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    return cleaned.strip(" .")[:100]


def story_id_from_input(text):
    """Return the story ID from an ID, story link or chapter link, or None if it's none of those."""
    text = text.strip()
    if text.isdigit():
        return text

    try:
        url = urlparse(text if "://" in text else f"https://{text}")
        host = (url.hostname or "").lower()
    except ValueError:
        return None
    if host != "wattpad.com" and not host.endswith(".wattpad.com"):
        return None

    story_match = re.search(r"/story/(\d+)", url.path)
    if story_match:
        return story_match.group(1)

    # Chapter links have the chapter's ID instead of the story's
    chapter_match = re.match(r"/(\d+)(?:[-/]|$)", url.path)
    if chapter_match:
        return get_story_id_for_part(chapter_match.group(1))
    return None


def ask_story_id():
    while True:
        story_id = story_id_from_input(input("Story ID or link: "))
        if story_id:
            return story_id
        print("That isn't a story ID or Wattpad link. Try 83744060 or https://www.wattpad.com/story/83744060.")


def ask_format():
    while True:
        file_format = input("Format (pdf/md): ").strip().lower().lstrip(".")
        if file_format in EXPORTERS:
            return file_format
        print('Please type "pdf" or "md".')


def ask_yes_no(question):
    while True:
        answer = input(f"{question} (y/n): ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print('Please type "y" or "n".')


def already_downloaded(story, story_id, file_format, one_file):
    """Return whether this story already has an export in this format and layout."""
    name = _safe_filename(story["title"]) or story_id
    if one_file:
        return (EXPORTS_DIR / f"{name}.{file_format}").exists()
    return any((EXPORTS_DIR / name).glob(f"*.{file_format}"))


def download_chapters(parts):
    """Yield (number, part, html) for each chapter that has text."""
    for number, part in enumerate(parts, start=1):
        if number > 1:
            time.sleep(DELAY_BETWEEN_CHAPTERS_SECONDS)

        html = get_chapter_html(part["id"])
        if not clean_html(html):
            print(f"  [{number}/{len(parts)}] Skipped, no text returned: {part['title']}")
            continue

        print(f"  [{number}/{len(parts)}] {part['title']}")
        yield number, part, html


def export_chapters(story, story_id, file_format):
    """Save each chapter of a story as its own file and return the folder and character count."""
    folder = EXPORTS_DIR / (_safe_filename(story["title"]) or story_id)
    folder.mkdir(parents=True, exist_ok=True)

    characters = 0
    for number, part, html in download_chapters(story["parts"]):
        filename = f"{number:02d} - {_safe_filename(part['title'])}.{file_format}"
        EXPORTERS[file_format](part["title"], html, folder / filename)
        characters += count_characters(html)
    return folder, characters


def export_single_file(story, story_id, file_format):
    """Save all of a story's chapters in one file and return its path and character count."""
    chapters = [(part["title"], html) for _, part, html in download_chapters(story["parts"])]
    if not chapters:
        raise ValueError("no chapters had any text, so nothing was saved")

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORTS_DIR / f"{_safe_filename(story['title']) or story_id}.{file_format}"
    STORY_EXPORTERS[file_format](story["title"], chapters, path)
    return path, sum(count_characters(html) for _, html in chapters)


def main():
    try:
        story_id = ask_story_id()
        file_format = ask_format()
        one_file = ask_yes_no("Put all chapters in one file?")

        story = get_story(story_id)
        print(f"\n{story['title']} ({len(story['parts'])} chapters)")
        if already_downloaded(story, story_id, file_format, one_file):
            if not ask_yes_no("Already downloaded. Download again?"):
                print("Kept your existing copy.")
                return

        export = export_single_file if one_file else export_chapters
        saved_to, characters = export(story, story_id, file_format)
    except KeyboardInterrupt:
        print("\nCancelled.")
    except (OSError, ValueError) as error:
        print(f"\nStopped: {error}")
    else:
        print(f"\nDone! Saved to {saved_to}")
        print(f"Characters: {characters:,}")


if __name__ == "__main__":
    main()
