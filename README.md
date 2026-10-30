# LBPC Pulpit Schedule — auto-updating calendar

This project turns the pulpit schedule into a calendar that people subscribe to once. Every hour, GitHub checks the LBPC shared drive for a newer version of the schedule. If it finds one, it rebuilds the calendar, and everyone's iPhone or Google Calendar picks up the change.

**Each Sunday has two events, 8:00–9:15 am and 11:00 am–12:15 pm.** Combined services (titles containing Combined, ACM, Anniversary or Easter), Good Friday and Christmas Eve are one event, 9:00–10:45 am. Watchnight is 10:30 pm–midnight. Anything else that isn't on a Sunday is an all-day event until a time is added to `SERVICE_TIMES` in `build_calendar.py`.

**Each event looks like this:**

- **Title:** `LBPC Worship: <sermon title> (<passage>)`
- **Description:**
  ```
  Speaker: Rev Seet
  Chairperson: Not confirmed
  Sub-theme: Redeeming the Time Begins with a Heart of Wisdom
  ```

The 2027 quarterly sub-themes are set at the top of `build_calendar.py` (`SUBTHEMES`):

| Quarter | Sub-theme |
|---|---|
| Jan–Mar | Redeeming the Time Begins with a Heart of Wisdom |
| Apr–Jun | Redeeming the Time by Living in God’s Presence |
| Jul–Sep | Redeeming the Time by Making Wise Choices |
| Oct–Dec | Redeeming the Time by Being Always Ready |

The chairperson shows as "Not confirmed" until a quarterly file lists one for that date.

## What's in here
- `schedule/baseline/` holds the full-year speaker schedule currently in use. `SOURCE.txt` records which Drive file it came from.
- `schedule/quarterly/` holds the quarterly files with chairpersons.
- `build_calendar.py` combines them and writes `docs/preaching.ics`.
- `fetch_from_drive.py` finds the latest versions in the Drive folder.
- `docs/index.html` is the page you share, with "Add to iPhone" and "Add to Google Calendar" buttons.
- `.github/workflows/update-calendar.yml` runs the Drive check every hour, and also whenever a file is uploaded to `schedule/`.

### Two kinds of schedule file

1. **Full-year schedule (baseline).** It supplies every date, speaker and sermon title.
2. **Quarterly files.** Each covers one quarter, with speakers, sermon titles and chairpersons. For the dates it covers, **the quarterly file wins**: its speaker, title and chairperson replace the full-year values. A blank cell keeps the full-year value. A date that isn't in the full-year schedule is added.
   - Quarterly files build up. The Q2 file doesn't affect Q1's dates.
   - If there are two versions of the same quarter, the newer one (higher version number in the name, otherwise the later one) is used for the dates it lists.

### How the full-year "latest version" is chosen
The workflow looks in the LBPC shared drive **only at files whose name starts with `Schedule of Pulpit Sermons`**. It picks the one with the **highest version number** in its name: `(v.10.0)` beats `(v.9.0)`, and `ver. 9.5` also works. If versions tie, the most recently modified file wins. Other files in the drive (prayer meeting schedule, budget, drafts, etc.) are ignored.

So when a new version is ready, save it to the shared drive with the same naming pattern and a higher version number. Word, PDF, Excel, Google Doc or Google Sheet all work, as long as the table has the same column headings (Date, Text, Title, Speaker…).

---

## One-time setup

### 1. Create the repository (5 min)
1. On GitHub, click **New repository**. Name it, for example, `pulpit-calendar`, and set it to **Public**. A free plan only publishes Pages from public repos, and the calendar link is public in any case.
2. Click **uploading an existing file** and drag in everything from this folder.
   *Mac users:* Finder hides the `.github` folder. Press **Cmd + Shift + .** to show it before dragging.
3. Commit.
4. Go to **Settings → Actions → General → Workflow permissions**, select **Read and write permissions**, and save.
5. Go to **Settings → Pages**. Set Source to **Deploy from a branch**, Branch to **main**, folder **/docs**, and save.

The page is live at `https://YOUR-USERNAME.github.io/pulpit-calendar/` within a minute. Share that link.

### 2. Give GitHub read access to the shared drive (10 min)
1. Go to <https://console.cloud.google.com> and create a project. Then go to **APIs & Services → Enable APIs and services** and enable **Google Drive API**.
2. Go to **IAM & Admin → Service Accounts → Create service account**. No roles are needed. Open it, then go to **Keys → Add key → Create new key → JSON**. This downloads a key file.
3. **Add the service account's email** (`…@….iam.gserviceaccount.com`) **to the shared drive as a Viewer.** This must be done by a shared-drive **Manager** (currently cseet@lifebpc.com). Content managers can't add members.
   *If Google blocks it, your Workspace admin needs to allow sharing with that address.*
4. In GitHub, go to **Settings → Secrets and variables → Actions → New repository secret**. Name it `GDRIVE_SA_JSON` and paste the whole contents of the JSON key file.
5. Go to **Actions → Update calendar → Run workflow** to test. The log lists which schedule files it found and which one it used.

*Optional:* if the schedules later move into their own folder, add a secret `GDRIVE_FOLDER_ID` with that folder's ID.

### 3. When the quarterly files start (2 min)
Go to **Settings → Secrets and variables → Actions → Variables tab → New repository variable**. Name it `QUARTERLY_NAME_PREFIX` and set its value to how the quarterly files' names begin (for example `Pulpit Roster`). Every file in the drive starting with that text is then used as a quarterly file. If its column headings differ from Date / Speaker / Title / Chairperson, the parser may need a small update.

---

## Good to know
- **Changes update, they don't duplicate.** Each event's ID is based on its date, so a changed speaker or title updates the existing event. A date removed from the schedule disappears from calendars.
- **Refresh speed:** iPhones follow the user's Calendar fetch setting. Google Calendar refreshes subscribed calendars on its own schedule, usually within a day.
- **Manual upload:** you can upload a full-year file into `schedule/baseline/` or a quarterly file into `schedule/quarterly/` on GitHub. The calendar rebuilds within a minute. With the Drive check on, `schedule/quarterly/` mirrors Drive, so put quarterly files in Drive rather than uploading them here.
- **If the hourly check stops:** GitHub pauses scheduled jobs in repos with no activity for 60 days. Go to **Actions → Update calendar** and click **Enable workflow**.
- **New schedule format:** if a version arrives with different column headings, the build will fail and GitHub emails the repo owner. The parser needs a small update for that format.
