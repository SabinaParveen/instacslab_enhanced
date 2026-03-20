# InstaPy — Enhanced Edition

An Instagram-like social platform built with Flask + PostgreSQL.

## New Features
- **Direct Messaging** — real-time chat between users (3-second polling), unread badge in navbar
- **Profile Editing** — update bio, email, avatar photo, and password
- **Message button** on every user's profile
- **Settings page** accessible from the navbar

---

## Local Development

### Requirements
- Python 3.10+
- PostgreSQL 14+

### Setup
```bash
# 1. Clone / extract the project
cd instacslab

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure the database (edit config.py or set env vars)
export DB_HOST=localhost
export DB_NAME=instacslab
export DB_USER=postgres
export DB_PASSWORD=yourpassword
export SECRET_KEY=any-long-random-string

# 5. Create the database in psql
createdb instacslab

# 6. Run the app (tables are auto-created on first start)
python app.py
```

Visit http://localhost:5000

---

## Deploy to Render (free tier)

### Option A — Render Blueprint (recommended, one-click)
1. Push this project to a **GitHub** (or GitLab) repository.
2. Go to https://dashboard.render.com → **New** → **Blueprint**.
3. Connect your repo — Render will read `render.yaml` and create:
   - A **Web Service** (Python / gunicorn)
   - A **PostgreSQL** database (free tier)
   - A **1 GB persistent disk** for uploaded images
4. Click **Apply**. The first deploy takes ~3 minutes.
5. Your public URL will be `https://instacslab.onrender.com` (or similar).

### Option B — Manual setup
1. **Create a PostgreSQL database** in Render dashboard → copy the *External* connection string.
2. **Create a Web Service**:
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT`
3. **Environment Variables** (in the service's Environment tab):
   | Key | Value |
   |-----|-------|
   | `DATABASE_URL` | paste the Postgres connection string |
   | `SECRET_KEY` | any long random string |
4. **(Optional but recommended)** Add a **Disk** (1 GB) mounted at `/opt/render/project/src/static/uploads` so uploaded images survive redeploys.
5. Deploy!

### Important notes for production
- The free Render web service **spins down after 15 min of inactivity** (cold start ~30 s).
- Free PostgreSQL databases expire after **90 days** — upgrade or back up before then.
- For production workloads consider using **Cloudinary** or **AWS S3** for image storage instead of local disk.
