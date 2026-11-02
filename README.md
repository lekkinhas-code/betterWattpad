# betterWattpad

A small command-line tool that saves public Wattpad stories as clean PDF or Markdown files for personal reading.

## Born in the Great AO3 Down

On 29 October 2026, Archive of Our Own went offline for maintenance that could last up to a month, and fic readers everywhere were left without their archive.

betterWattpad was started on 2 November 2026, four days into the outage. If you're reading this after AO3 came back: welcome, and we made it.

## Features

- Download a whole story from its ID, its link or a link to any chapter
- Save it as PDF or Markdown
- Keep all chapters in one file, or save one file per chapter
- Keep bold, italic and line breaks from the original chapter
- Keep underline and text alignment in PDFs
- Add a first page with the story's title, author, last published date, tags and link
- Use the story and chapter titles as headings
- Start each chapter on a new page in single-file PDFs
- Show the story's total character count in the terminal when the export finishes

## Getting started

You'll need Python. The project has been tested on Python 3.13.

```
pip install -r requirements.txt
python main.py
```

The program then asks three questions:

```
Story ID or link: https://www.wattpad.com/story/83744060-story-title
Format (pdf/md): pdf
Put all chapters in one file? (y/n): y
```

You can paste a link to the story or to any of its chapters, or type just the story ID. The ID is the number in the story's URL: for `wattpad.com/story/83744060-story-title`, it's `83744060`. A chapter link always downloads the whole story, not just that chapter.

## Where files are saved

Everything goes in the `exports/` folder, which git ignores:

| Option | Example |
|---|---|
| One file | `exports/Story Title (83744060).pdf` |
| One file per chapter | `exports/Story Title (83744060)/01 - Chapter Title.pdf` |

The story ID in the name keeps different stories with the same title apart.

If you already have that story in the same format and layout, the program asks before downloading it again. Answering `y` overwrites the earlier files.

## Project structure

| File | Purpose |
|---|---|
| `main.py` | Asks the questions and runs the export |
| `wattpad_api.py` | Gets story details and chapter HTML from Wattpad |
| `chapter_export.py` | Cleans the HTML and writes the PDF and Markdown files |

## Known limitations

- **One-file exports are all or nothing:** the file is only written after every chapter has downloaded, so an interrupted run saves nothing.
- **Images are dropped:** only the text is kept.
- **Markdown formatting:** Markdown has no underline or text alignment, so those are lost. Page breaks use a small HTML tag that only takes effect when printing or exporting from a tool that supports it.
- **PDF characters:** the Helvetica font doesn't include emoji, Cyrillic, Chinese and similar characters, so they won't display properly. Markdown keeps them.
- **Paid and restricted chapters:** these aren't supported or tested. Chapters that come back empty are skipped and listed in the terminal.
- **It may break without warning:** Wattpad doesn't document the endpoints this project uses, and a change on their side could stop it working.

## Disclaimer

This is an unofficial personal project, and it isn't affiliated with or endorsed by Wattpad.

Wattpad's [Terms of Service](https://policies.wattpad.com/terms) prohibit scraping, including for personal use, so use this tool at your own risk. Stories belong to their authors: don't share or republish what you download, and if a site blocks the tool, stop rather than trying to get around it.
