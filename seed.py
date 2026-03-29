"""
seed.py — Populate the database with demo users, posts, likes,
           comments, and follow relationships for lab testing.

Usage:
    python seed.py
"""

import psycopg2
from werkzeug.security import generate_password_hash
from config import Config

DEMO_USERS = [
    ("alice",   "alice@lab.com",   "pass1234", "Photography enthusiast 📷"),
    ("bob",     "bob@lab.com",     "pass1234", "Coffee & code ☕"),
    ("carol",   "carol@lab.com",   "pass1234", "Traveller | Explorer 🌍"),
    ("dave",    "dave@lab.com",    "pass1234", "Just here for the memes 😄"),
]

# Public-domain placeholder images (Lorem Picsum — no auth required)
DEMO_POSTS = [
    (1, "https://picsum.photos/seed/a1/600/600", "Golden hour never gets old 🌅"),
    (1, "https://picsum.photos/seed/a2/600/600", "Morning walk vibes"),
    (2, "https://picsum.photos/seed/b1/600/600", "Brewed to perfection ☕"),
    (2, "https://picsum.photos/seed/b2/600/600", "Late night debugging session…"),
    (3, "https://picsum.photos/seed/c1/600/600", "Streets of Rome 🇮🇹"),
    (3, "https://picsum.photos/seed/c2/600/600", "Somewhere over the Alps ✈️"),
    (4, "https://picsum.photos/seed/d1/600/600", "When the tests finally pass 🎉"),
]

DEMO_COMMENTS = [
    (1, 2, "Absolutely stunning! 😍"),
    (1, 3, "Where was this taken?"),
    (2, 4, "So peaceful"),
    (3, 1, "I need this coffee right now"),
    (5, 1, "Bucket list destination!"),
    (5, 4, "Incredible shot 🔥"),
    (7, 2, "Haha same energy every single time"),
]

# (follower_id, followed_id)
DEMO_FOLLOWS = [
    (1, 2), (1, 3),
    (2, 1), (2, 3),
    (3, 1), (3, 4),
    (4, 2), (4, 3),
]

# (post_id, user_id)
DEMO_LIKES = [
    (1, 2), (1, 3), (1, 4),
    (2, 3),
    (3, 1), (3, 4),
    (4, 1),
    (5, 1), (5, 2), (5, 4),
    (6, 3),
    (7, 1), (7, 2), (7, 3),
]


def seed():
    conn = psycopg2.connect(
        host=Config.DB_HOST, port=Config.DB_PORT,
        dbname=Config.DB_NAME, user=Config.DB_USER,
        password=Config.DB_PASSWORD,
    )
    cur = conn.cursor()

    print("🌱  Seeding database…")

    # Users
    for username, email, password, bio in DEMO_USERS:
        cur.execute(
            """INSERT INTO users (username, email, password_hash, bio)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (username) DO NOTHING""",
            (username, email, generate_password_hash(password), bio)
        )
    print(f"   ✅  {len(DEMO_USERS)} users")

    # Posts (image_url stored as remote URL for demo; real uploads go to static/uploads/)
    for user_id, image_url, caption in DEMO_POSTS:
        cur.execute(
            """INSERT INTO posts (user_id, image_url, caption)
               VALUES (%s, %s, %s)""",
            (user_id, image_url, caption)
        )
    print(f"   ✅  {len(DEMO_POSTS)} posts")

    # Followers
    for follower_id, followed_id in DEMO_FOLLOWS:
        cur.execute(
            """INSERT INTO followers (follower_id, followed_id)
               VALUES (%s, %s) ON CONFLICT DO NOTHING""",
            (follower_id, followed_id)
        )
    print(f"   ✅  {len(DEMO_FOLLOWS)} follow relationships")

    # Likes
    for post_id, user_id in DEMO_LIKES:
        cur.execute(
            """INSERT INTO likes (post_id, user_id)
               VALUES (%s, %s) ON CONFLICT DO NOTHING""",
            (post_id, user_id)
        )
    print(f"   ✅  {len(DEMO_LIKES)} likes")

    # Comments
    for post_id, user_id, body in DEMO_COMMENTS:
        cur.execute(
            "INSERT INTO comments (post_id, user_id, body) VALUES (%s, %s, %s)",
            (post_id, user_id, body)
        )
    print(f"   ✅  {len(DEMO_COMMENTS)} comments")

    conn.commit()
    cur.close(); conn.close()
    print("\n🎉  Done! Log in with any demo user — password is: pass1234")
    print("     Users: alice, bob, carol, dave")


if __name__ == '__main__':
    seed()
