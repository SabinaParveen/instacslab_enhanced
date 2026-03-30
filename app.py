"""
InstaPy - Instagram-like web application
Enhanced with: Direct Messaging + Profile Editing
"""

import os
import re
import uuid
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse

from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import psycopg2
from psycopg2.extras import RealDictCursor

from config import Config

# ──────────────────────────────────────────────
# App Initialization
# ──────────────────────────────────────────────
app = Flask(__name__)
app.config.from_object(Config)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


# ──────────────────────────────────────────────
# Database Connection
# ──────────────────────────────────────────────
def get_db():
    """Open a new PostgreSQL connection."""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        # Render supplies postgres:// but psycopg2 needs postgresql://
        if db_url.startswith('postgres://'):
            db_url = 'postgresql://' + db_url[len('postgres://'):]
        parsed = urlparse(db_url)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            dbname=parsed.path.lstrip('/'),
            user=parsed.username,
            password=parsed.password,
            sslmode='require'
        )
    else:
        conn = psycopg2.connect(
            host=app.config['DB_HOST'],
            port=app.config['DB_PORT'],
            dbname=app.config['DB_NAME'],
            user=app.config['DB_USER'],
            password=app.config['DB_PASSWORD'],
        )
    conn.autocommit = False
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(open('models/schema.sql').read())
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database tables initialised.")


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def unread_message_count(uid):
    """Return number of unread messages for the logged-in user."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM messages WHERE receiver_id=%s AND is_read=FALSE", (uid,))
        count = cur.fetchone()[0]
        cur.close(); conn.close()
        return count
    except Exception:
        return 0


@app.context_processor
def inject_globals():
    uid = session.get('user_id')
    return dict(unread_count=unread_message_count(uid) if uid else 0)


# ──────────────────────────────────────────────
# Auth Routes
# ──────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email    = request.form['email'].strip().lower()
        password = request.form['password']
        bio      = request.form.get('bio', '').strip()

        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return redirect(url_for('register'))

        hashed = generate_password_hash(password)
        conn = get_db(); cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (username, email, password_hash, bio) VALUES (%s,%s,%s,%s)",
                (username, email, hashed, bio)
            )
            conn.commit()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        except psycopg2.IntegrityError:
            conn.rollback()
            flash('Username or email already taken.', 'danger')
        finally:
            cur.close(); conn.close()

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cur.fetchone()
        cur.close(); conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id']  = user['id']
            session['username'] = user['username']
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('feed'))

        flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ──────────────────────────────────────────────
# Feed
# ──────────────────────────────────────────────
@app.route('/')
@login_required
def feed():
    uid  = session['user_id']
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT p.id, p.image_url, p.caption, p.created_at,
               u.id AS author_id, u.username, u.avatar_url,
               (SELECT COUNT(*) FROM likes    WHERE post_id = p.id)     AS like_count,
               (SELECT COUNT(*) FROM comments WHERE post_id = p.id)     AS comment_count,
               EXISTS(SELECT 1 FROM likes WHERE post_id = p.id AND user_id = %s) AS liked
        FROM posts p
        JOIN users u ON u.id = p.user_id
        WHERE p.user_id = %s
           OR p.user_id IN (SELECT followed_id FROM followers WHERE follower_id = %s)
        ORDER BY p.created_at DESC LIMIT 50
    """, (uid, uid, uid))
    posts = cur.fetchall()

    post_ids = [p['id'] for p in posts]
    comments_map = {}
    if post_ids:
        fmt = ','.join(['%s'] * len(post_ids))
        cur.execute(f"""
            SELECT c.post_id, c.body, c.created_at, u.username
            FROM comments c JOIN users u ON u.id = c.user_id
            WHERE c.post_id IN ({fmt}) ORDER BY c.created_at ASC
        """, post_ids)
        for row in cur.fetchall():
            comments_map.setdefault(row['post_id'], []).append(row)

    cur.close(); conn.close()
    return render_template('feed.html', posts=posts, comments_map=comments_map)


# ──────────────────────────────────────────────
# Upload
# ──────────────────────────────────────────────
@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        caption = request.form.get('caption', '').strip()
        file    = request.files.get('image')

        if not file or not allowed_file(file.filename):
            flash('Please upload a valid image (png, jpg, jpeg, gif, webp).', 'danger')
            return redirect(url_for('upload'))

        ext      = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)

        image_url = f"/static/uploads/{filename}"
        conn = get_db(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO posts (user_id, image_url, caption) VALUES (%s,%s,%s)",
            (session['user_id'], image_url, caption)
        )
        conn.commit()
        cur.close(); conn.close()

        flash('Post uploaded!', 'success')
        return redirect(url_for('feed'))

    return render_template('upload.html')


# ──────────────────────────────────────────────
# Like (AJAX)
# ──────────────────────────────────────────────
@app.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like(post_id):
    uid  = session['user_id']
    conn = get_db(); cur = conn.cursor()

    cur.execute("SELECT 1 FROM likes WHERE post_id=%s AND user_id=%s", (post_id, uid))
    if cur.fetchone():
        cur.execute("DELETE FROM likes WHERE post_id=%s AND user_id=%s", (post_id, uid))
        liked = False
    else:
        cur.execute("INSERT INTO likes (post_id, user_id) VALUES (%s,%s)", (post_id, uid))
        liked = True

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM likes WHERE post_id=%s", (post_id,))
    count = cur.fetchone()[0]
    cur.close(); conn.close()
    return jsonify({'liked': liked, 'count': count})


# ──────────────────────────────────────────────
# Comment (AJAX)
# ──────────────────────────────────────────────
@app.route('/comment/<int:post_id>', methods=['POST'])
@login_required
def comment(post_id):
    body = request.json.get('body', '').strip()
    if not body:
        return jsonify({'error': 'Empty comment'}), 400

    uid  = session['user_id']
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "INSERT INTO comments (post_id, user_id, body) VALUES (%s,%s,%s) RETURNING id, created_at",
        (post_id, uid, body)
    )
    row = cur.fetchone()
    conn.commit()
    cur.close(); conn.close()

    return jsonify({
        'id':         row['id'],
        'username':   session['username'],
        'body':       body,
        'created_at': row['created_at'].strftime('%b %d, %Y')
    })


# ──────────────────────────────────────────────
# Follow / Unfollow (AJAX)
# ──────────────────────────────────────────────
@app.route('/follow/<int:target_id>', methods=['POST'])
@login_required
def follow(target_id):
    uid = session['user_id']
    if uid == target_id:
        return jsonify({'error': 'Cannot follow yourself'}), 400

    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT 1 FROM followers WHERE follower_id=%s AND followed_id=%s", (uid, target_id))
    if cur.fetchone():
        cur.execute("DELETE FROM followers WHERE follower_id=%s AND followed_id=%s", (uid, target_id))
        following = False
    else:
        cur.execute("INSERT INTO followers (follower_id, followed_id) VALUES (%s,%s)", (uid, target_id))
        following = True

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM followers WHERE followed_id=%s", (target_id,))
    count = cur.fetchone()[0]
    cur.close(); conn.close()
    return jsonify({'following': following, 'follower_count': count})


# ──────────────────────────────────────────────
# Profile (view)
# ──────────────────────────────────────────────
@app.route('/profile/<username>')
@login_required
def profile(username):
    uid  = session['user_id']
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT id, username, bio, avatar_url, created_at FROM users WHERE username=%s", (username,))
    owner = cur.fetchone()
    if not owner:
        flash('User not found.', 'danger')
        return redirect(url_for('feed'))

    cur.execute("SELECT COUNT(*) AS cnt FROM followers WHERE followed_id=%s", (owner['id'],))
    follower_count = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) AS cnt FROM followers WHERE follower_id=%s", (owner['id'],))
    following_count = cur.fetchone()['cnt']

    cur.execute("""
        SELECT p.id, p.image_url, p.caption, p.created_at,
               (SELECT COUNT(*) FROM likes WHERE post_id = p.id) AS like_count
        FROM posts p WHERE p.user_id=%s ORDER BY p.created_at DESC
    """, (owner['id'],))
    posts = cur.fetchall()

    cur.execute("SELECT 1 FROM followers WHERE follower_id=%s AND followed_id=%s", (uid, owner['id']))
    is_following = cur.fetchone() is not None
    cur.close(); conn.close()

    return render_template('profile.html',
                           owner=owner, posts=posts,
                           follower_count=follower_count,
                           following_count=following_count,
                           is_following=is_following,
                           is_own_profile=(uid == owner['id']))


# ──────────────────────────────────────────────
# Profile Edit
# ──────────────────────────────────────────────
@app.route('/settings/profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    uid  = session['user_id']
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)

    if request.method == 'POST':
        bio      = request.form.get('bio', '').strip()
        email    = request.form.get('email', '').strip().lower()
        new_pass = request.form.get('new_password', '').strip()
        avatar   = request.files.get('avatar')

        updates = ['bio=%s', 'email=%s']
        values  = [bio, email]

        # Handle avatar upload
        if avatar and avatar.filename and allowed_file(avatar.filename):
            ext      = avatar.filename.rsplit('.', 1)[1].lower()
            filename = f"avatar_{uid}_{uuid.uuid4().hex}.{ext}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            avatar.save(save_path)
            updates.append('avatar_url=%s')
            values.append(f'/static/uploads/{filename}')

        # Handle password change
        if new_pass:
            if len(new_pass) < 6:
                flash('New password must be at least 6 characters.', 'danger')
                return redirect(url_for('edit_profile'))
            cur2 = conn.cursor()
            cur2.execute("SELECT password_hash FROM users WHERE id=%s", (uid,))
            row = cur2.fetchone()
            current_pass = request.form.get('current_password', '')
            if not check_password_hash(row['password_hash'], current_pass):
                flash('Current password is incorrect.', 'danger')
                cur2.close(); cur.close(); conn.close()
                return redirect(url_for('edit_profile'))
            updates.append('password_hash=%s')
            values.append(generate_password_hash(new_pass))
            cur2.close()

        values.append(uid)
        try:
            cur.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id=%s",
                values
            )
            conn.commit()
            flash('Profile updated!', 'success')
        except psycopg2.IntegrityError:
            conn.rollback()
            flash('Email already in use by another account.', 'danger')
        finally:
            cur.close(); conn.close()
        return redirect(url_for('edit_profile'))

    cur.execute("SELECT id, username, email, bio, avatar_url FROM users WHERE id=%s", (uid,))
    user = cur.fetchone()
    cur.close(); conn.close()
    return render_template('edit_profile.html', user=user)


# ──────────────────────────────────────────────
# Messages — Inbox
# ──────────────────────────────────────────────
@app.route('/messages')
@login_required
def messages_inbox():
    uid  = session['user_id']
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get all conversations: last message + unread count per partner
    cur.execute("""
        WITH convos AS (
            SELECT
                CASE WHEN sender_id=%s THEN receiver_id ELSE sender_id END AS partner_id,
                MAX(created_at) AS last_at
            FROM messages
            WHERE sender_id=%s OR receiver_id=%s
            GROUP BY partner_id
        )
        SELECT u.id, u.username, u.avatar_url,
               c.last_at,
               (SELECT body FROM messages
                WHERE (sender_id=%s AND receiver_id=u.id) OR (sender_id=u.id AND receiver_id=%s)
                ORDER BY created_at DESC LIMIT 1) AS last_body,
               (SELECT COUNT(*) FROM messages
                WHERE sender_id=u.id AND receiver_id=%s AND is_read=FALSE) AS unread
        FROM convos c
        JOIN users u ON u.id = c.partner_id
        ORDER BY c.last_at DESC
    """, (uid, uid, uid, uid, uid, uid))
    conversations = cur.fetchall()
    cur.close(); conn.close()

    return render_template('messages_inbox.html', conversations=conversations)


# ──────────────────────────────────────────────
# Messages — Conversation thread
# ──────────────────────────────────────────────
@app.route('/messages/<int:other_id>')
@login_required
def messages_thread(other_id):
    uid  = session['user_id']
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT id, username, avatar_url FROM users WHERE id=%s", (other_id,))
    other = cur.fetchone()
    if not other:
        flash('User not found.', 'danger')
        return redirect(url_for('messages_inbox'))

    # Mark received messages as read
    cur2 = conn.cursor()
    cur2.execute(
        "UPDATE messages SET is_read=TRUE WHERE sender_id=%s AND receiver_id=%s AND is_read=FALSE",
        (other_id, uid)
    )
    conn.commit()
    cur2.close()

    # Fetch conversation messages
    cur.execute("""
        SELECT m.id, m.body, m.created_at, m.is_read,
               m.sender_id, u.username, u.avatar_url
        FROM messages m JOIN users u ON u.id = m.sender_id
        WHERE (m.sender_id=%s AND m.receiver_id=%s)
           OR (m.sender_id=%s AND m.receiver_id=%s)
        ORDER BY m.created_at ASC
    """, (uid, other_id, other_id, uid))
    msgs = cur.fetchall()
    cur.close(); conn.close()

    return render_template('messages_thread.html', other=other, msgs=msgs)


# ──────────────────────────────────────────────
# Messages — Send (AJAX + form fallback)
# ──────────────────────────────────────────────
@app.route('/messages/<int:other_id>/send', methods=['POST'])
@login_required
def messages_send(other_id):
    uid  = session['user_id']
    if uid == other_id:
        if request.is_json:
            return jsonify({'error': 'Cannot message yourself'}), 400
        flash('You cannot message yourself.', 'danger')
        return redirect(url_for('messages_inbox'))

    body = (request.json or {}).get('body') or request.form.get('body', '')
    body = body.strip()
    if not body:
        if request.is_json:
            return jsonify({'error': 'Empty message'}), 400
        return redirect(url_for('messages_thread', other_id=other_id))

    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "INSERT INTO messages (sender_id, receiver_id, body) VALUES (%s,%s,%s) RETURNING id, created_at",
        (uid, other_id, body)
    )
    row = cur.fetchone()
    conn.commit()
    cur.close(); conn.close()

    if request.is_json:
        return jsonify({
            'id':         row['id'],
            'body':       body,
            'created_at': row['created_at'].strftime('%b %d, %Y %H:%M'),
            'sender_id':  uid,
            'username':   session['username']
        })
    return redirect(url_for('messages_thread', other_id=other_id))


# ──────────────────────────────────────────────
# Messages — Poll for new messages (AJAX)
# ──────────────────────────────────────────────
@app.route('/messages/<int:other_id>/poll')
@login_required
def messages_poll(other_id):
    uid    = session['user_id']
    after  = request.args.get('after', 0, type=int)   # last message id client knows
    conn   = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT m.id, m.body, m.created_at, m.sender_id, u.username, u.avatar_url
        FROM messages m JOIN users u ON u.id = m.sender_id
        WHERE ((m.sender_id=%s AND m.receiver_id=%s) OR (m.sender_id=%s AND m.receiver_id=%s))
          AND m.id > %s
        ORDER BY m.created_at ASC
    """, (uid, other_id, other_id, uid, after))
    rows = cur.fetchall()

    # Mark new incoming messages read
    if rows:
        cur2 = conn.cursor()
        cur2.execute(
            "UPDATE messages SET is_read=TRUE WHERE sender_id=%s AND receiver_id=%s AND is_read=FALSE",
            (other_id, uid)
        )
        conn.commit()
        cur2.close()

    cur.close(); conn.close()
    return jsonify([{
        'id':         r['id'],
        'body':       r['body'],
        'created_at': r['created_at'].strftime('%b %d, %Y %H:%M'),
        'sender_id':  r['sender_id'],
        'username':   r['username'],
        'avatar_url': r['avatar_url']
    } for r in rows])


# ──────────────────────────────────────────────
# Unread count (AJAX — navbar badge)
# ──────────────────────────────────────────────
@app.route('/messages/unread-count')
@login_required
def messages_unread_count():
    uid = session['user_id']
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM messages WHERE receiver_id=%s AND is_read=FALSE", (uid,))
    count = cur.fetchone()[0]
    cur.close(); conn.close()
    return jsonify({'count': count})


# ──────────────────────────────────────────────
# Search (AJAX)
# ──────────────────────────────────────────────
@app.route('/search')
@login_required
def search():
    q    = request.args.get('q', '').strip()
    conn = get_db(); cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT id, username, avatar_url FROM users WHERE username ILIKE %s LIMIT 10",
        (f'%{q}%',)
    )
    results = cur.fetchall()
    cur.close(); conn.close()
    return jsonify(results)


# ──────────────────────────────────────────────
# Delete Post
# ──────────────────────────────────────────────
@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    uid  = session['user_id']
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT user_id, image_url FROM posts WHERE id=%s", (post_id,))
    post = cur.fetchone()
    if not post:
        flash('Post not found.', 'danger')
        cur.close(); conn.close()
        return redirect(url_for('feed'))
    if post[0] != uid:
        flash('You can only delete your own posts.', 'danger')
        cur.close(); conn.close()
        return redirect(url_for('feed'))

    image_url = post[1]
    if image_url.startswith('/static/uploads/'):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], image_url.split('/')[-1])
        if os.path.exists(filepath):
            os.remove(filepath)

    cur.execute("DELETE FROM posts WHERE id=%s", (post_id,))
    conn.commit()
    cur.close(); conn.close()
    flash('Post deleted.', 'info')
    return redirect(url_for('profile', username=session['username']))


# ──────────────────────────────────────────────
# Error Handlers
# ──────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# ──────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    with app.app_context():
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
