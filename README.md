# Videoflix Backend

A Django REST API for a video streaming platform. It handles user authentication
(JWT via HttpOnly cookies), video management, and on-upload transcoding of
uploaded videos into adaptive **HLS** streams using FFmpeg. Heavy work
(transcoding, thumbnail extraction) runs asynchronously through **Redis Queue
(RQ)**.

## Tech Stack

- **Python** 3.12
- **Django** 6.0 + **Django REST Framework**
- **SimpleJWT** for authentication (tokens stored in HttpOnly cookies)
- **PostgreSQL** as the database
- **Redis** for caching and as the RQ broker
- **django-rq** / **RQ** for background jobs
- **FFmpeg** for HLS conversion and thumbnail extraction
- **Gunicorn** + **WhiteNoise** for serving
- **Docker** / Docker Compose

## Project Structure

```
backend/
├── core/                 # Django project (settings, urls, wsgi/asgi)
├── auth_app/             # Registration, activation, login/logout, password reset
│   └── api/              # Serializers, views, cookie JWT auth, urls
├── video_app/            # Video model, HLS endpoints
│   └── api/
│       ├── service.py    # FFmpeg HLS conversion + thumbnail extraction
│       ├── signals.py    # Enqueues RQ jobs on upload, cleans up on delete
│       ├── utils.py      # Path helpers for playlists/segments
│       └── views.py      # List, m3u8 playlist, segment endpoints
├── media/                # Uploaded videos, thumbnails, generated HLS output
├── static/               # Collected static files
├── docker-compose.yml
├── backend.Dockerfile
├── backend.entrypoint.sh # Waits for DB, migrates, creates superuser, starts worker + gunicorn
└── requirements.txt
```

## Getting Started (Docker — recommended)

Docker is the intended way to run this project. The compose stack provides the
web service, PostgreSQL, and Redis.

### 1. Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose

### 2. Create the `.env` file

Copy the template and fill in your values:

```bash
cp .env.template .env
```

See [Environment Variables](#environment-variables) below for what each entry
means. At minimum set `DB_NAME`, `DB_USER`, `DB_PASSWORD`, and a `SECRET_KEY`.

### 3. Build and start

```bash
docker compose up --build
```

The entrypoint script (`backend.entrypoint.sh`) automatically:

1. Waits for PostgreSQL to become reachable.
2. Runs `collectstatic`, `makemigrations`, and `migrate`.
3. Creates a Django superuser from the `DJANGO_SUPERUSER_*` variables (if it
   doesn't already exist).
4. Starts an RQ worker (`rqworker default`) in the background.
5. Starts Gunicorn on port **8000**.

The API is then available at **http://localhost:8000/**, and the Django admin at
**http://localhost:8000/admin/**.

### 4. Stop

```bash
docker compose down          # keep data
docker compose down -v       # also remove volumes (db, redis, media, static)
```

## Getting Started (Local, without Docker)

You can run the project directly if you provide your own PostgreSQL and Redis
instances, and have **FFmpeg** installed and on your `PATH`.

# 1. Create and activate a virtual environment
```bash
python -m venv .venv
source 
 .venv/bin/activate        
Windows: 
 .venv\Scripts\activate
```
# 2. Install dependencies
```bash
pip install -r requirements.txt
```
# 3. Configure
```bash
 .env — point DB_HOST and REDIS_HOST at localhost
    (the defaults "db" / "redis" are Docker service names)
```
# 4. Apply migrations
```bash
python manage.py migrate
```

# 5. In one terminal: start the RQ worker (required for uploads to process)
```bash
python manage.py rqworker default
```
# 6. In another terminal: run the dev server
```bash
python manage.py runserver
```

> **Note:** FFmpeg must be installed locally (e.g. `apt install ffmpeg`,
> `brew install ffmpeg`, or `choco install ffmpeg`). Without the worker running,
> uploaded videos will not be transcoded.

## Environment Variables

All variables are read from `.env`. A template is provided in `.env.template`.

### Django / Superuser

| Variable                   | Description                                          | Example                          |
| -------------------------- | ---------------------------------------------------- | -------------------------------- |
| `SECRET_KEY`               | Django secret key — **change for production**        | `django-insecure-...`            |
| `DEBUG`                    | Debug mode                                           | `True`                           |
| `ALLOWED_HOSTS`            | Comma-separated allowed hosts                        | `localhost,127.0.0.1`            |
| `CSRF_TRUSTED_ORIGINS`     | Comma-separated trusted origins                      | `http://localhost:5500`          |
| `DJANGO_SUPERUSER_USERNAME`| Superuser created on first start                     | `admin`                          |
| `DJANGO_SUPERUSER_EMAIL`   | Superuser email                                      | `admin@example.com`              |
| `DJANGO_SUPERUSER_PASSWORD`| Superuser password                                   | `adminpassword`                  |
| `FRONTEND_URL`             | Base URL used to build activation / reset links      | `http://localhost:4200`          |

### Database (PostgreSQL)

| Variable      | Description                | Docker default |
| ------------- | -------------------------- | -------------- |
| `DB_NAME`     | Database name              | —              |
| `DB_USER`     | Database user              | —              |
| `DB_PASSWORD` | Database password          | —              |
| `DB_HOST`     | Database host              | `db`           |
| `DB_PORT`     | Database port              | `5432`         |

### Redis

| Variable         | Description                          | Docker default            |
| ---------------- | ------------------------------------ | ------------------------- |
| `REDIS_HOST`     | Redis host (used by RQ)              | `redis`                   |
| `REDIS_PORT`     | Redis port                           | `6379`                    |
| `REDIS_DB`       | Redis DB index for RQ                | `0`                       |
| `REDIS_LOCATION` | Full Redis URL for the Django cache  | `redis://redis:6379/1`    |

### Email (SMTP)

| Variable              | Description                       |
| --------------------- | --------------------------------- |
| `EMAIL_HOST`          | SMTP host                         |
| `EMAIL_PORT`          | SMTP port                         |
| `EMAIL_HOST_USER`     | SMTP user                         |
| `EMAIL_HOST_PASSWORD` | SMTP password                     |
| `EMAIL_USE_TLS`       | Use TLS (`True`/`False`)          |
| `EMAIL_USE_SSL`       | Use SSL (`True`/`False`)          |
| `DEFAULT_FROM_EMAIL`  | Default sender address            |

> When `DB_HOST`/`REDIS_HOST` are set to the Docker service names (`db`, `redis`),
> the app only resolves them correctly **inside** the compose network. For local
> runs, set them to `localhost`.

## API Endpoints

All endpoints are prefixed with `/api/`. Authenticated endpoints expect a valid
JWT access token, which is sent automatically via the HttpOnly cookie set at login.

### Authentication (`auth_app`)

| Method | Path                                      | Description                               |
| ------ | ----------------------------------------- | ----------------------------------------- |
| POST   | `/api/register/`                          | Register a new user (sends activation email) |
| GET    | `/api/activate/<uidb64>/<token>/`         | Activate an account                       |
| POST   | `/api/login/`                             | Log in — sets JWT cookies                 |
| POST   | `/api/logout/`                            | Log out — blacklists token, clears cookies|
| POST   | `/api/token/refresh/`                     | Refresh the access token from the cookie  |
| POST   | `/api/password_reset/`                    | Request a password reset email            |
| POST   | `/api/password_confirm/<uidb64>/<token>/` | Set a new password                        |

### Videos (`video_app`)

| Method | Path                                                 | Description                          |
| ------ | --------------------------------------------------- | ------------------------------------ |
| GET    | `/api/video/`                                        | List all videos                      |
| GET    | `/api/video/<movie_id>/<resolution>/index.m3u8`     | HLS playlist for a resolution        |
| GET    | `/api/video/<movie_id>/<resolution>/<segment>/`     | A single `.ts` HLS segment           |

`<resolution>` is one of `480p`, `720p`, `1080p`.

## Notable Features

### HLS Transcoding

Uploaded videos are converted into [HTTP Live Streaming](https://developer.apple.com/streaming/)
output so clients can stream adaptively.

- On upload, FFmpeg transcodes the source into three renditions — **480p, 720p,
  and 1080p** — each as a `.m3u8` playlist plus `.ts` segments (10s per segment).
- Output is written to `media/videos/<video_id>/<resolution>/`
  (`index.m3u8` + `seg0000.ts`, `seg0001.ts`, …).
- A thumbnail is extracted from the frame at `00:00:01` and stored on the
  `Video.thumbnail` field.
- Playlists and segments are served through the authenticated endpoints above
  (see `video_app/api/views.py`), not as raw static files.

The conversion logic lives in [video_app/api/service.py](video_app/api/service.py).

### Background Jobs with RQ

Transcoding is too slow to run inside a request, so it is offloaded to a worker.

- A `post_save` signal on the `Video` model enqueues `convert_video_to_hls` onto
  the `default` queue whenever a new video is created
  (see [video_app/api/signals.py](video_app/api/signals.py)).
- The queue is backed by Redis and configured under `RQ_QUEUES` in
  [core/settings.py](core/settings.py) (default job timeout: 900s).
- In Docker, the worker is started automatically by the entrypoint
  (`python manage.py rqworker default`). Locally you must start it yourself.
- A `post_delete` signal removes the source file and the generated HLS directory
  when a video is deleted.

You can inspect queues via Django RQ's admin integration or the `rq info` CLI.

### Cookie-based JWT Auth

Authentication uses SimpleJWT, but tokens are delivered as **HttpOnly cookies**
rather than in the response body, via a custom authentication class
(`auth_app.api.authentication.CookieJWTAuthentication`). Cookies are marked
`secure` outside of `DEBUG` and use `SameSite=Lax`. Token blacklisting is enabled
for logout. Access tokens live 30 minutes; refresh tokens 1 day.

## Running Tests

```bash
# Docker
docker compose exec web python manage.py test

# Local
python manage.py test
```
