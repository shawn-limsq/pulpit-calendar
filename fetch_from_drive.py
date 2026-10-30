#!/usr/bin/env python3
"""Download the pulpit schedules from Google Drive.

Full-year schedule: of the files whose name starts with BASELINE_PREFIX, the
one with the highest version number in its name ("(v.10.0)" beats "(v.9.0)";
ties go to the most recently modified) is saved to schedule/baseline/.

Quarterly files (chairpersons): every file whose name starts with
QUARTERLY_PREFIX is mirrored into schedule/quarterly/. The builder decides
which one wins for each date. Set QUARTERLY_PREFIX once the naming is known.

Other files in the folder are ignored.

Needs one GitHub Actions secret:
  GDRIVE_SA_JSON  - the full JSON key of a Google service account that has
                    Viewer access to the folder / shared drive
Optional overrides (secrets or env):
  GDRIVE_FOLDER_ID, SCHEDULE_NAME_PREFIX, QUARTERLY_NAME_PREFIX

Exits quietly if the key is missing, so manual uploads still work.
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASELINE_DIR = ROOT / "schedule" / "baseline"
QUARTERLY_DIR = ROOT / "schedule" / "quarterly"
API = "https://www.googleapis.com/drive/v3/files"

# The LBPC shared drive that holds the schedule (folder ID or shared-drive ID)
DEFAULT_FOLDER_ID = "0AKMYXza3wZmJUk9PVA"
DEFAULT_NAME_PREFIX = "Schedule of Pulpit Sermons"
# TODO: set to the start of the quarterly files' names when the first one arrives
DEFAULT_QUARTERLY_PREFIX = ""

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOWNLOAD = {DOCX: ".docx", XLSX: ".xlsx", "application/pdf": ".pdf", "text/csv": ".csv"}
EXPORT = {  # native Google files are exported
    "application/vnd.google-apps.document": (DOCX, ".docx"),
    "application/vnd.google-apps.spreadsheet": (XLSX, ".xlsx"),
}
from build_calendar import version_of  # noqa: E402  (same rule as the builder)


def list_folder(session, folder_id):
    params = {
        "q": f"'{folder_id}' in parents and trashed = false",
        "fields": "nextPageToken, files(id,name,mimeType,modifiedTime)",
        "pageSize": 200,
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
    }
    if folder_id.startswith("0A"):  # root of a shared drive
        params.update(corpora="drive", driveId=folder_id)
    files, token = [], None
    while True:
        if token:
            params["pageToken"] = token
        r = session.get(API, params=params)
        r.raise_for_status()
        data = r.json()
        files += data.get("files", [])
        token = data.get("nextPageToken")
        if not token:
            return files


def download(session, meta):
    mime = meta["mimeType"]
    if mime in EXPORT:
        export_mime, ext = EXPORT[mime]
        r = session.get(f"{API}/{meta['id']}/export", params={"mimeType": export_mime})
    else:
        ext = DOWNLOAD[mime]
        r = session.get(f"{API}/{meta['id']}", params={"alt": "media", "supportsAllDrives": "true"})
    r.raise_for_status()
    return r.content, ext


def write_if_changed(path, content):
    if path.exists() and path.read_bytes() == content:
        return False
    path.write_bytes(content)
    return True


def matching(files, prefix):
    prefix = prefix.lower()
    return [f for f in files if f["name"].lower().startswith(prefix)
            and (f["mimeType"] in DOWNLOAD or f["mimeType"] in EXPORT)]


def safe_stem(name):
    stem = re.sub(r"\.(docx|pdf|xlsx|csv)$", "", name, flags=re.I)
    return re.sub(r"[^\w().\- ]+", "_", stem).strip()


def main():
    sa = os.environ.get("GDRIVE_SA_JSON")
    if not sa:
        print("GDRIVE_SA_JSON not set; skipping Drive check.")
        return
    folder_id = os.environ.get("GDRIVE_FOLDER_ID") or DEFAULT_FOLDER_ID
    base_prefix = os.environ.get("SCHEDULE_NAME_PREFIX") or DEFAULT_NAME_PREFIX
    q_prefix = os.environ.get("QUARTERLY_NAME_PREFIX") or DEFAULT_QUARTERLY_PREFIX

    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession

    creds = service_account.Credentials.from_service_account_info(
        json.loads(sa), scopes=["https://www.googleapis.com/auth/drive.readonly"])
    s = AuthorizedSession(creds)
    files = list_folder(s, folder_id)

    # --- full-year schedule ---
    candidates = matching(files, base_prefix)
    if not candidates:
        sys.exit(f"No file starting with '{base_prefix}' found in the Drive folder. "
                 "Check the service account has access and the file name.")
    candidates.sort(key=lambda f: (version_of(f["name"]), f["modifiedTime"]), reverse=True)
    meta = candidates[0]
    print("Full-year candidates:", ", ".join(f["name"] for f in candidates))
    content, ext = download(s, meta)
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    target = BASELINE_DIR / f"schedule{ext}"
    if target.exists() and target.read_bytes() == content:
        print(f"Full-year: using '{meta['name']}' (unchanged).")
    else:
        for old in BASELINE_DIR.glob("schedule.*"):
            old.unlink()
        target.write_bytes(content)
        print(f"Full-year: updated from '{meta['name']}'.")
    (BASELINE_DIR / "SOURCE.txt").write_text(f"{meta['name']}\nmodified {meta['modifiedTime']}\n")

    # --- quarterly files ---
    if not q_prefix:
        print("Quarterly file name not configured yet; skipping.")
        return
    QUARTERLY_DIR.mkdir(parents=True, exist_ok=True)
    keep = set()
    for f in matching(files, q_prefix):
        content, ext = download(s, f)
        local = QUARTERLY_DIR / f"{safe_stem(f['name'])}{ext}"
        keep.add(local.name)
        print(("Quarterly: updated " if write_if_changed(local, content) else "Quarterly: unchanged ") + f["name"])
    for old in QUARTERLY_DIR.iterdir():  # mirror Drive: drop files removed there
        if old.suffix.lower() in (".docx", ".pdf", ".xlsx", ".csv") and old.name not in keep:
            old.unlink()
            print(f"Quarterly: removed {old.name} (no longer in Drive)")


if __name__ == "__main__":
    main()
