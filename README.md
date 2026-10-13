# cp-calendar

Generates per-studio `.ics` calendar feeds from CorePower Yoga's public
class-schedule data, hosted on GitHub Pages, so you can subscribe to a
studio's upcoming classes directly in Google Calendar (or any calendar app).

Not an official CorePower product — this talks to the same public,
unauthenticated endpoint CorePower's own website uses to render its
schedule pages (`POST https://api2.corepoweryoga.com/elastic`).

## How it works

- `studios.json` lists the studios to generate feeds for (name, slug,
  Zenoti center ID).
- A GitHub Actions workflow (`.github/workflows/sync.yml`) runs every 4
  hours (and on-demand via "Run workflow"), regenerating each studio's
  `.ics` file under `docs/` and committing it if anything changed.
- GitHub Pages serves `docs/` as a static site, so each file gets a stable
  public URL like:

  ```
  https://<your-username>.github.io/<repo>/north-boulder.ics
  ```

- `docs/index.html` lists every feed's URL and how many classes it has.

Each event's `UID` is derived from CorePower's stable `session_id`, so
re-running the sync updates events in place instead of duplicating them.
Every event also carries a direct link to that class's live page on
corepoweryoga.com, and a "synced as of" timestamp in its description —
useful because Google Calendar polls subscribed URLs on its own schedule
(often not for several hours), so the feed file can be fresher than what
Google is currently showing you.

## One-time setup

1. Push this repo to GitHub as a **public** repo (GitHub Pages' free tier
   requires it).
2. In the repo's **Settings → Pages**, set the source to the `docs/`
   folder on the default branch.
3. Wait for the first workflow run (or trigger it manually from the
   **Actions** tab → "Sync CorePower schedule" → "Run workflow").
4. Visit `https://<your-username>.github.io/<repo>/` to confirm the feeds
   are live, then in Google Calendar: **Settings → Add calendar → From
   URL**, and paste in the `.ics` URL for each studio you want to see.
   Toggle each one on/off anytime from Google Calendar's sidebar — no
   repo changes needed.

## Adding another studio

1. Find the studio on corepoweryoga.com and note its city/slug (visible
   in the page URL, e.g. `/yoga-studios/co/boulder/south-boulder`).
2. Look up its Zenoti center ID via CorePower's public Contentful studio
   directory:

   ```bash
   curl -s "https://cdn.contentful.com/spaces/go5rjm58sryl/environments/master/entries?access_token=6b61TxCL9VW-1xwx-Oy4x9OOGMweRyBSDhaXCZM4d-o&content_type=studios&limit=400&select=fields.title,fields.slug,fields.zenotiCenterId" \
     | python3 -c "import json,sys; [print(i['fields']) for i in json.load(sys.stdin)['items']]" \
     | grep -i "<studio name or city>"
   ```

3. Add an entry to `studios.json`:

   ```json
   { "name": "<Display Name>", "slug": "<url-safe-slug>", "zenotiCenterId": "<id from step 2>" }
   ```

4. Commit and push — the next scheduled run (or a manual "Run workflow")
   will generate its feed.

## Local development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/generate_all.py
```

Output lands in `docs/*.ics` and `docs/index.html`.
