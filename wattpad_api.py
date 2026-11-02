import gzip
import json
from urllib.request import Request, urlopen

BASE_URL = "https://www.wattpad.com"
USER_AGENT = "betterWattpad/0.1"
TIMEOUT_SECONDS = 30


def _get(path):
    request = Request(BASE_URL + path, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read()
    # storytext responses come back gzipped, so check for the gzip signature
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    return body.decode("utf-8")


def get_story(story_id):
    """Return a story's id, title, numParts and parts (each with id and title)."""
    path = f"/api/v3/stories/{story_id}?fields=id,title,numParts,parts(id,title)"
    return json.loads(_get(path))


def get_story_id_for_part(part_id):
    """Return the ID of the story that a chapter belongs to."""
    return json.loads(_get(f"/v4/parts/{part_id}?fields=group(id)"))["group"]["id"]


def get_chapter_html(part_id):
    """Return a chapter's text as HTML. part_id comes from get_story()'s parts."""
    return _get(f"/apiv2/storytext?id={part_id}")
