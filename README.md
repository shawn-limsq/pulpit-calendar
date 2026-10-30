# LBPC Pulpit Schedule — auto-updating calendar

This project turns the pulpit schedule (Word, PDF, Excel or CSV) into a calendar that people subscribe to once. Whenever the schedule changes, GitHub rebuilds the calendar, and everyone's iPhone or Google Calendar picks up the change.

- `schedule/` holds the current schedule file.
- `build_calendar.py` reads the newest file in `schedule/` and writes `docs/preaching.ics`. Every service becomes an **all-day event** titled like *Rev Seet: The Heart Matters (Lk 8:1-15)*. The passage, chairperson, series, notes and movement go in the event details.
- `docs/index.html` is the page you share. It has "Add to iPhone" and "Add to Google Calendar" buttons.
- `.github/workflows/update-calendar.yml` rebuilds the calendar when a new file is uploaded, and once an hour checks Google Drive (optional).
- `fetch_from_drive.py` downloads the schedule from Google Drive (optional).

Columns are matched **by their header names**, not their position, so the new format with a **Chairperson** column works without any code changes. These headers are recognised (case doesn't matter):

| Field | Header can contain |
|---|---|
| Date (required) | date |
| Passage | text, passage, scripture, reading |
| Sermon title | title, sermon, topic, theme |
| Speaker | speaker, preacher |
| Chairperson | chair, presiding, worship leader, liturgist |
| Notes | notes, remarks, description |
| Movement | movement, events |

Dates like `03 Jan 27`, `3 January 2027`, `Sun, 3rd Jan 2027`, `03/01/2027` and real Excel dates all work. Full-width rows (such as the quarter headings) are recorded as the event's "Series".

---

## One-time setup (about 10 minutes)

### 1. Create the repository
1. On GitHub, click **New repository**. Name it, for example, `pulpit-calendar`, and set it to **Public**. A free GitHub plan only publishes Pages from public repositories, and the calendar link is public in any case.
2. Click **uploading an existing file** and drag in everything from this folder.
   - **Mac users:** Finder hides the `.github` folder. Press **Cmd + Shift + .** in Finder to show it before dragging. Or, after uploading, choose **Add file → Create new file**, type `.github/workflows/update-calendar.yml` as the name, and paste in that file's contents.
3. Commit.

### 2. Allow the workflow to save updates
**Settings → Actions → General → Workflow permissions →** select **Read and write permissions** → Save.

### 3. Turn on the web page
**Settings → Pages → Build and deployment →** Source: **Deploy from a branch**, Branch: **main**, folder **/docs** → Save.

After a minute, your page is live at:
`https://YOUR-USERNAME.github.io/pulpit-calendar/`

Share **that page link** with the congregation. Each person taps the button for their calendar once.

---

## Updating the schedule

### Option A — upload the new file (simplest)
In the repo, open `schedule/` → **Add file → Upload files** → drop in the new schedule → Commit.
The newest file wins, so you can leave older ones there, though deleting them keeps things tidy. The calendar rebuilds within about a minute (check the **Actions** tab).

### Option B — fully automatic from Google Drive
The workflow checks Drive every hour and rebuilds only when something changed. This requires a Google service account:

1. In <https://console.cloud.google.com>, create a project → **APIs & Services → Enable APIs** → enable **Google Drive API**.
2. **IAM & Admin → Service Accounts → Create**. No roles are needed. Open it → **Keys → Add key → JSON**, which downloads a key file.
3. In Google Drive, **share the schedule file (or its folder) with the service account's email** (`…@….iam.gserviceaccount.com`) as **Viewer**.
   *If sharing is blocked, your Google Workspace admin may need to allow sharing with that address.*
4. In GitHub: **Settings → Secrets and variables → Actions → New repository secret**:
   - `GDRIVE_SA_JSON` → paste the whole contents of the JSON key file
   - and **one** of:
     - `GDRIVE_FILE_ID` → `1E-5hytSfSSO6TtWtK7un_dBUo_p53DLq`. Use this if the schedule is always edited in this same file.
     - `GDRIVE_FOLDER_ID` → the ID of a Drive folder. Use this if each new version is a *new* file (for example, the upcoming format with the chairperson). The newest Word, PDF, Excel, Google Doc or Google Sheet in the folder is used.
5. **Actions → Update calendar → Run workflow** to test it.

---

## Good to know
- **Changes update, they don't duplicate.** Each event's ID is based on its date, so changing the speaker or title for a date updates the existing event. Removing a date from the schedule removes it from calendars.
- **Refresh speed:** iPhones follow the user's Calendar fetch setting. Google Calendar refreshes subscribed calendars on its own schedule, usually within a day, and this can't be changed.
- **GitHub pauses hourly jobs** in a repo with no activity for 60 days. If Drive sync stops, open **Actions → Update calendar** and click **Enable workflow**. Uploading a file always triggers a build regardless.
- **Run it locally:** `pip install -r requirements.txt && python build_calendar.py`
