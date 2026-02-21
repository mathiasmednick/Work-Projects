# GC Scheduler

Internal Django tool for a commercial GC scheduling department (manager + schedulers).

## Setup

```bash
cd gc_scheduler
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # optional
python manage.py seed_scheduler    # sample data: manager/devpass, scheduler1/devpass
```

## Run

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py runserver 0.0.0.0:8000
```

Open http://127.0.0.1:8000/ and log in. Managers see Dashboard and Projects; schedulers see My Work and Time.

## Deploy on PythonAnywhere (free tier)

See [DEPLOY_PYTHONANYWHERE.md](DEPLOY_PYTHONANYWHERE.md) for WSGI config, static files, and SQLite setup.
