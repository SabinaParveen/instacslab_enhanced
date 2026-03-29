/* ══════════════════════════════════════════════════════
   InstaPy  –  Frontend JavaScript
   Handles: likes, comments, follow/unfollow, search,
            upload preview, flash dismissal
   ══════════════════════════════════════════════════════ */

"use strict";

// ── Like Toggle ───────────────────────────────────────
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.like-btn');
  if (!btn) return;

  const postId = btn.dataset.postId;
  btn.disabled = true;

  try {
    const res  = await fetch(`/like/${postId}`, { method: 'POST' });
    const data = await res.json();

    btn.classList.toggle('liked', data.liked);
    btn.querySelector('.like-count').textContent = data.count;

    // Heart pulse animation
    const svg = btn.querySelector('svg');
    svg.style.transform = 'scale(1.4)';
    setTimeout(() => { svg.style.transform = ''; }, 200);
  } catch {
    console.error('Like request failed');
  } finally {
    btn.disabled = false;
  }
});


// ── Comment Submission ────────────────────────────────
document.addEventListener('submit', async (e) => {
  const form = e.target.closest('.comment-form');
  if (!form) return;
  e.preventDefault();

  const input  = form.querySelector('.comment-input');
  const submit = form.querySelector('.comment-submit');
  const body   = input.value.trim();
  if (!body) return;

  const postId = form.dataset.postId;
  submit.disabled = true;

  try {
    const res  = await fetch(`/comment/${postId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ body }),
    });
    const data = await res.json();
    if (data.error) return;

    const list = form.closest('.post-card').querySelector('.comments-list');
    const item = document.createElement('div');
    item.className = 'comment-item';
    item.innerHTML = `<strong>${escHtml(data.username)}</strong>${escHtml(data.body)}
                      <span class="comment-time">${data.created_at}</span>`;
    list.appendChild(item);
    item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    // Update comment count badge
    const badge = form.closest('.post-card').querySelector('.comment-count');
    if (badge) badge.textContent = parseInt(badge.textContent || '0') + 1;

    input.value = '';
  } catch {
    console.error('Comment request failed');
  } finally {
    submit.disabled = false;
  }
});

// Enable / disable comment submit button dynamically
document.addEventListener('input', (e) => {
  if (!e.target.classList.contains('comment-input')) return;
  const btn = e.target.closest('.comment-form')?.querySelector('.comment-submit');
  if (btn) btn.disabled = !e.target.value.trim();
});


// ── Follow / Unfollow ─────────────────────────────────
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.follow-btn');
  if (!btn) return;

  const targetId = btn.dataset.userId;
  btn.disabled = true;

  try {
    const res  = await fetch(`/follow/${targetId}`, { method: 'POST' });
    const data = await res.json();

    btn.classList.toggle('following', data.following);
    btn.classList.toggle('not-following', !data.following);
    btn.textContent = data.following ? 'Following' : 'Follow';

    const counter = document.getElementById('follower-count');
    if (counter) counter.textContent = data.follower_count;
  } catch {
    console.error('Follow request failed');
  } finally {
    btn.disabled = false;
  }
});


// ── Username Search ───────────────────────────────────
(function() {
  const searchInput = document.getElementById('search-input');
  const dropdown    = document.getElementById('search-dropdown');
  if (!searchInput || !dropdown) return;

  let debounceTimer;

  searchInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const q = searchInput.value.trim();
    if (q.length < 1) { dropdown.style.display = 'none'; return; }

    debounceTimer = setTimeout(async () => {
      try {
        const res   = await fetch(`/search?q=${encodeURIComponent(q)}`);
        const users = await res.json();
        renderDropdown(users);
      } catch { /* ignore */ }
    }, 250);
  });

  function renderDropdown(users) {
    dropdown.innerHTML = '';
    if (!users.length) { dropdown.style.display = 'none'; return; }

    users.forEach(u => {
      const item = document.createElement('div');
      item.className = 'search-result-item';
      item.innerHTML = `
        <img src="${u.avatar_url || '/static/images/default_avatar.png'}" alt="">
        <span>@${escHtml(u.username)}</span>`;
      item.addEventListener('click', () => {
        window.location.href = `/profile/${encodeURIComponent(u.username)}`;
      });
      dropdown.appendChild(item);
    });
    dropdown.style.display = 'block';
  }

  document.addEventListener('click', (e) => {
    if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
      dropdown.style.display = 'none';
    }
  });
})();


// ── Image Upload Preview ──────────────────────────────
(function() {
  const fileInput  = document.getElementById('image-input');
  const dropzone   = document.getElementById('upload-dropzone');
  const preview    = document.getElementById('image-preview');
  if (!fileInput) return;

  fileInput.addEventListener('change', showPreview);

  dropzone?.addEventListener('dragover', (e) => {
    e.preventDefault(); dropzone.classList.add('dragover');
  });
  dropzone?.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone?.addEventListener('drop', (e) => {
    e.preventDefault(); dropzone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
      showPreview();
    }
  });

  function showPreview() {
    const file = fileInput.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      preview.src = ev.target.result;
      preview.style.display = 'block';
    };
    reader.readAsDataURL(file);
  }
})();


// ── Flash Auto-dismiss ────────────────────────────────
setTimeout(() => {
  document.querySelectorAll('.flash').forEach(el => {
    el.style.transition = 'opacity .4s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 400);
  });
}, 4000);


// ── Utility ───────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
