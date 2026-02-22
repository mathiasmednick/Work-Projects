# Deploying GC Scheduler on PythonAnywhere (free tier)

This app is set up to run on PythonAnywhere's free tier using **SQLite** (no MySQL required). The database file lives in the project directory.

## Assumptions

- Free account at [pythonanywhere.com](https://www.pythonanywhere.com)
- Code deployed at `/home/<username>/gc_scheduler/` (clone or upload)
- SQLite database at `/home/<username>/gc_scheduler/db.sqlite3`
- Python 3.10 (or the version offered on the Web tab)

## Data safety

The database file `db.sqlite3` is **not** tracked by Git (it is listed in `.gitignore`). This means:

- **Normal redeploy** (`git pull` → `migrate` → `collectstatic` → Reload) **does not** replace or wipe the live database. It only updates code files and applies new migrations to the existing DB.
- **DO NOT** copy your local `db.sqlite3` to the server, run `manage.py flush`, run `manage.py seed_scheduler` on the live site (it resets data), or delete/overwrite the server's `db.sqlite3`. Any of these would destroy live data.
- **Migrations are safe.** Running `python manage.py migrate --noinput` only adds new tables/columns; it never drops existing data.

**Bottom line:** Push code to GitHub, pull on PythonAnywhere, run migrate + collectstatic, click Reload. Your data stays exactly as it was.

## Steps

### 1. Upload code

In a Bash console:

```bash
cd ~
git clone <your-repo-url> gc_scheduler
# or upload via Files tab / pip install git+...
cd gc_scheduler
```

### 2. Virtualenv and dependencies

```bash
mkvirtualenv --python=/usr/bin/python3.10 gc_scheduler
pip install -r requirements.txt
```

If `mkvirtualenv` is not found, see [Installing virtualenvwrapper](https://help.pythonanywhere.com/pages/InstallingVirtualenvWrapper) on the PythonAnywhere help site.

### 3. Web app (Manual configuration)

- Open the **Web** tab and create a new web app.
- Choose **Manual configuration** (not the Django shortcut).
- Select the same Python version as your virtualenv (e.g. 3.10).
- In **Virtualenv**, enter: `gc_scheduler` (or the full path `~/.virtualenvs/gc_scheduler`).
- Optionally set **Source code** and **Working directory** to `/home/<username>/gc_scheduler`.

### 4. WSGI file

Click the link to the WSGI file (e.g. `/var/www/<username>_pythonanywhere_com_wsgi.py`). Replace its contents with the Django section only, for example:

```python
import os
import sys

path = '/home/<username>/gc_scheduler'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'gc_scheduler.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

Replace `<username>` with your PythonAnywhere username. Save the file.

### 5. Static files

- In your project, `STATIC_ROOT` is set to `os.path.join(BASE_DIR, 'static')` in `gc_scheduler/settings.py` (i.e. `/home/<username>/gc_scheduler/static` after `collectstatic`).
- In a Bash console:

  ```bash
  cd /home/<username>/gc_scheduler
  python manage.py collectstatic --noinput
  ```

- In the **Web** tab, under **Static files**, add a mapping:
  - **URL**: `/static/`
  - **Directory**: `/home/<username>/gc_scheduler/static`

### 6. Database and superuser

In a Bash console:

```bash
cd /home/<username>/gc_scheduler
python manage.py migrate
python manage.py createsuperuser   # optional, for admin
python manage.py seed_scheduler    # optional, for sample dev data
```

SQLite is stored in the project folder; no separate database server is needed. The web process has write access to the project directory in your home folder.

### 7. Reload and test

- Click **Reload** for your web app on the Web tab.
- Visit `https://<username>.pythonanywhere.com/` and log in (e.g. `manager` / `devpass` if you ran `seed_scheduler`).
- Admin: `https://<username>.pythonanywhere.com/admin/`

## Security notes for production

- **Environment variables (required):** The app reads `DJANGO_DEBUG` and `DJANGO_SECRET_KEY` from the environment. On PythonAnywhere, set these before the app loads:
  - **Option A (recommended):** In the **Web** tab, under your app, find **Code** → **Environment variables** (or the equivalent). Add:
    - `DJANGO_DEBUG` = `False`
    - `DJANGO_SECRET_KEY` = a long random string (e.g. from `python -c "import secrets; print(secrets.token_urlsafe(50))"`). Never commit this value.
  - **Option B:** In your WSGI file, add near the top (before `get_wsgi_application`):  
    `os.environ['DJANGO_DEBUG'] = 'False'` and `os.environ['DJANGO_SECRET_KEY'] = 'your-secret-key-here'`.
- Add your PythonAnywhere host to `ALLOWED_HOSTS` (already set for `mathiasmednick.pythonanywhere.com`).
- Use HTTPS (PythonAnywhere provides it for your domain).

## Redeploy (after code changes)

In a Bash console on PythonAnywhere:

```bash
cd ~/gc_scheduler
git pull   # or re-upload your code
workon gc_scheduler   # or: source ~/.virtualenvs/gc_scheduler/bin/activate
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

Then click **Reload** for your web app on the **Web** tab.

> **Your live database (`db.sqlite3`) is not in the repo.** The steps above do not replace it — only new migrations are applied to the existing DB. All your data stays intact.

### Post-deploy verification

After every deploy, check these items before moving on:

1. **Static files load**: Open any page (e.g. `/`) and verify the sidebar is dark blue with styled nav links. If the page is unstyled plain text, static files are not being served.
2. **Check browser devtools**: Open the Network tab, reload the page, and confirm `base.css` and `components.css` return HTTP 200 (not 404 or 403).
3. **Static mapping**: On the PythonAnywhere **Web** tab, verify the static mapping:
   - URL: `/static/`
   - Directory: `/home/<username>/gc_scheduler/static`
4. **Dashboard check**: Log in as a manager and confirm the Manager Overview shows the grey top bar, stat cards, and tables.
5. **Nested page check**: Navigate to at least one nested URL (e.g. Weather or Whiteboard) and confirm CSS still loads correctly.

If styles break after a deploy, the fix is almost always: run `collectstatic --noinput` again + Reload on the Web tab.

### Production readiness checklist

Before considering the site fully deployed:

1. **Environment:** `DJANGO_DEBUG=False` and `DJANGO_SECRET_KEY` are set (see Security notes). Reload the web app after setting them.
2. **No debug pages:** Trigger a 404 (e.g. visit a non-existent URL) and confirm a generic error page is shown, not a Django debug stack trace.
3. **Login and roles:** Log in as manager and as scheduler; confirm dashboard, tasks, and timesheets behave correctly.
4. **Time entries:** As manager, select the scheduler in Timesheets, then delete or edit a scheduler time entry; confirm the confirm page loads and that after delete/edit you return to the scheduler's list. As scheduler, delete your own entry and confirm it works.

## Free tier limits

- One web app, limited CPU and disk. See [Free accounts](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/) for current limits.
- SQLite is suitable for low concurrency; for heavier use consider upgrading and switching to MySQL/PostgreSQL if needed.
