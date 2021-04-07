#!/usr/bin/env python
import fileinput
import os
import sys

import gitlab

BOT_USERNAME = os.getenv("BOT_USERNAME")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CI_SERVER_URL = os.getenv("CI_SERVER_URL")
CI_PROJECT_ID = os.getenv("CI_PROJECT_ID")
CI_MERGE_REQUEST_IID = os.getenv("CI_MERGE_REQUEST_IID")


def main():
    if not all(
        [BOT_USERNAME, BOT_TOKEN, CI_SERVER_URL, CI_PROJECT_ID, CI_MERGE_REQUEST_IID]
    ):
        print(
            "Missing BOT_USERNAME or BOT_TOKEN or CI_SERVER_URL or CI_PROJECT_ID or CI_MERGE_REQUEST_IID.",
            file=sys.stderr,
        )
        sys.exit(1)

    gl = gitlab.Gitlab(CI_SERVER_URL, private_token=BOT_TOKEN)
    projects = gl.projects.get(CI_PROJECT_ID)
    mr = projects.mergerequests.get(CI_MERGE_REQUEST_IID)
    notes = mr.notes.list(all=True)
    existing_note = None
    for note in notes:
        if note.attributes["author"]["username"] == BOT_USERNAME:
            existing_note = note
            break

    message = "```\n"
    for line in fileinput.input():
        message += line
    message += "```"

    if existing_note:
        existing_note.body = message
        existing_note.save()
    else:
        mr.notes.create({"body": message})


if __name__ == "__main__":
    main()
