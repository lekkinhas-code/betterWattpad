import re
import time
from pathlib import Path

from chapter_export import chapter_to_markdown, chapter_to_pdf, clean_html, story_to_markdown, story_to_pdf
from wattpad_api import get_chapter_html, get_story

DELAY_BETWEEN_CHAPTERS_SECONDS = 1
EXPORTS_DIR = Path(__file__).parent / "exports"
EXPORTERS = {"pdf": chapter_to_pdf, "md": chapter_to_markdown}
STORY_EXPORTERS = {"pdf": story_to_pdf, "md": story_to_markdown}


def _safe_filename(name):
    """Remove the characters Windows doesn't allow in file and folder names."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    return cleaned.strip(" .")[:100]


def ask_story_id():
    while True:
        story_id = input("Story ID: ").strip()
        if story_id.isdigit():
            return story_id
        print("The ID should only contain numbers, like 83744060.")


def ask_format():
    while True:
        file_format = input("Format (pdf/md): ").strip().lower().lstrip(".")
        if file_format in EXPORTERS:
            return file_format
        print('Please type "pdf" or "md".')


def ask_one_file():
    while True:
        answer = input("Put all chapters in one file? (y/n): ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print('Please type "y" or "n".')


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
    """Save each chapter of a story as its own file and return the folder."""
    folder = EXPORTS_DIR / (_safe_filename(story["title"]) or story_id)
    folder.mkdir(parents=True, exist_ok=True)

    for number, part, html in download_chapters(story["parts"]):
        filename = f"{number:02d} - {_safe_filename(part['title'])}.{file_format}"
        EXPORTERS[file_format](part["title"], html, folder / filename)
    return folder


def export_single_file(story, story_id, file_format):
    """Save all of a story's chapters in one file and return its path."""
    chapters = [(part["title"], html) for _, part, html in download_chapters(story["parts"])]
    if not chapters:
        raise ValueError("no chapters had any text, so nothing was saved")

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORTS_DIR / f"{_safe_filename(story['title']) or story_id}.{file_format}"
    STORY_EXPORTERS[file_format](story["title"], chapters, path)
    return path


def main():
    try:
        story_id = ask_story_id()
        file_format = ask_format()
        one_file = ask_one_file()

        story = get_story(story_id)
        print(f"\n{story['title']} ({len(story['parts'])} chapters)")
        export = export_single_file if one_file else export_chapters
        saved_to = export(story, story_id, file_format)
    except KeyboardInterrupt:
        print("\nCancelled.")
    except (OSError, ValueError) as error:
        print(f"\nStopped: {error}")
    else:
        print(f"\nDone! Saved to {saved_to}")


if __name__ == "__main__":
    main()
