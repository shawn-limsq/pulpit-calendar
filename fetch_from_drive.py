#!/usr/bin/env python3
"""Download the latest schedule from Google Drive into schedule/.

Needs two environment variables (set as GitHub Actions secrets):
  GDRIVE_SA_JSON   - the full JSON key of a Google service account
  GDRIVE_FILE_ID   - the Drive file ID of the schedule
                     (or GDRIVE_FOLDER_ID to always take the newest file in a folder)

Share the file (or folder) with the service account's email as Viewer.
Exits quietly if the secrets are missing, so the workflow still works with
manual uploads only.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "schedule"
API = "https://www.googleapis.com/drive/v3/files"
SUPPORTED = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "text/csv": ".csv",
}
# Native Google files are exported to an equivalent format
EXPORT = {
    "application/vnd.google-apps.document": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    "application/vnd.google-apps.spreadsheet": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
}


def main():
    sa = os.environ.get("GDRIVE_SA_JSON")
    file_id = os.environ.get("GDRIVE_FILE_ID")
    folder_id = os.environ.get("GDRIVE_FOLDER_ID")
    if not sa or not (file_id or folder_id):
        print("Drive secrets not set; skipping Drive sync.")
        return

    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession

    creds = service_account.Credentials.from_service_account_info(
        json.loads(sa), scopes=["https://www.googleapis.com/auth/drive.readonly"])
    s = AuthorizedSession(creds)
    common = {"supportsAllDrives": "true"}

    if folder_id:
        r = s.get(API, params={**common, "includeItemsFromAllDrives": "true",
                               "q": f"'{folder_id}' in parents and trashed = false",
                               "orderBy": "modifiedTime desc", "pageSize": 20,
                               "fields": "files(id,name,mimeType,modifiedTime)"})
        r.raise_for_status()
        files = [f for f in r.json()["files"] if f["mimeType"] in SUPPORTED or f["mimeType"] in EXPORT]
        if not files:
            sys.exit("No supported schedule file found in the Drive folder.")
        meta = files[0]
    else:
        r = s.get(f"{API}/{file_id}", params={**common, "fields": "id,name,mimeType,modifiedTime"})
        r.raise_for_status()
        meta = r.json()

    mime = meta["mimeType"]
    if mime in EXPORT:
        export_mime, ext = EXPORT[mime]
        r = s.get(f"{API}/{meta['id']}/export", params={"mimeType": export_mime})
    elif mime in SUPPORTED:
        ext = SUPPORTED[mime]
        r = s.get(f"{API}/{meta['id']}", params={**common, "alt": "media"})
    else:
        sys.exit(f"Unsupported file type in Drive: {mime}")
    r.raise_for_status()

    target = DEST / f"schedule{ext}"
    if target.exists() and target.read_bytes() == r.content:
        print(f"No change in '{meta['name']}'.")
        return
    DEST.mkdir(exist_ok=True)
    # Keep only one schedule file so the builder always uses the Drive copy
    for old in DEST.glob("schedule.*"):
        old.unlink()
    target.write_bytes(r.content)
    print(f"Updated from Drive: '{meta['name']}' (modified {meta['modifiedTime']}).")


if __name__ == "__main__":
    main()
