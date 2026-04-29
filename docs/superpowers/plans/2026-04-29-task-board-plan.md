# 内网任务发布与监控系统 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建轻量级内网任务发布与监控 Web 应用，支持脚本任务发布、并行执行、自动验收、单页看板。

**Architecture:** Flask 提供 HTTP API，SQLite 存储任务状态，ThreadPoolExecutor 并行执行 subprocess 脚本，Tkinter 托盘管理生命周期，单 HTML 文件内嵌 CSS/JS 作为前端。

**Tech Stack:** Python 3.12, Flask 3.x, sqlite3, threading, subprocess, Tkinter

---

### Task 1: 项目脚手架

**Files:**
- Create: `requirements.txt`
- Create: `config.json`

- [ ] **Step 1: 创建 requirements.txt**

```txt
flask>=3.0
```

- [ ] **Step 2: 创建 config.json**

```json
{
  "bindings": [
    {"assignee": "user1", "designs": ["芯片A", "芯片B"]},
    {"assignee": "user2", "designs": ["芯片A"]}
  ],
  "password": "admin123"
}
```

- [ ] **Step 3: 创建 templates 目录**

```bash
mkdir templates
```

---

### Task 2: 数据库初始化与配置加载

**Files:**
- Create: `models.py`

- [ ] **Step 1: 编写 models.py 骨架、init_db、load_config**

```python
import sqlite3
import json
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tasks.db')
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS task (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        detail TEXT DEFAULT '',
        script_path TEXT NOT NULL,
        accept_path TEXT NOT NULL,
        assignee TEXT NOT NULL,
        design TEXT NOT NULL,
        status TEXT DEFAULT 'Pending',
        log TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )''')
    conn.commit()
    conn.close()


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_bindings():
    return load_config().get('bindings', [])


def verify_password(password):
    return load_config().get('password', '') == password
```

- [ ] **Step 2: 验证 DB 初始化**

```bash
python -c "import models; models.init_db(); print('DB OK:', models.DB_PATH)"
```

---

### Task 3: Task CRUD 操作

**Files:**
- Modify: `models.py` — 追加以下函数

- [ ] **Step 1: 追加 create_task, get_tasks, get_task, update_task, delete_task, get_tasks_since, get_status_counts**

```python
def create_task(name, detail, script_path, accept_path, assignee, design):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO task (name, detail, script_path, accept_path, assignee, design, status, log, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (name, detail, script_path, accept_path, assignee, design, 'Pending', '', now, now)
    )
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    return task_id


def get_tasks(status=None):
    conn = get_db()
    if status:
        rows = conn.execute('SELECT * FROM task WHERE status = ? ORDER BY id DESC', (status,)).fetchall()
    else:
        rows = conn.execute('SELECT * FROM task ORDER BY id DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_task(task_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM task WHERE id = ?', (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_task(task_id, **kwargs):
    if not kwargs:
        return
    sets = ', '.join(f'{k} = ?' for k in kwargs)
    vals = list(kwargs.values()) + [task_id]
    conn = get_db()
    conn.execute(f'UPDATE task SET {sets} WHERE id = ?', vals)
    conn.commit()
    conn.close()


def delete_task(task_id):
    conn = get_db()
    conn.execute('DELETE FROM task WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()


def get_tasks_since(timestamp):
    conn = get_db()
    rows = conn.execute('SELECT * FROM task WHERE updated_at > ? ORDER BY id DESC', (timestamp,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_status_counts():
    conn = get_db()
    counts = {}
    for s in ['Pending', 'Running', 'Success', 'Failed']:
        counts[s] = conn.execute('SELECT COUNT(*) FROM task WHERE status = ?', (s,)).fetchone()[0]
    conn.close()
    return counts
```

- [ ] **Step 2: 验证 CRUD — 创建并查询一条记录**

```bash
python -c "
import models
models.init_db()
tid = models.create_task('test', 'detail', 'script.sh', 'out.log', 'user1', '芯片A')
t = models.get_task(tid)
print('Created:', t['name'], t['status'])
models.update_task(tid, status='Success')
t = models.get_task(tid)
print('Updated:', t['status'])
models.delete_task(tid)
print('Deleted, remaining:', len(models.get_tasks()))
"
```

---

### Task 4: 执行引擎

**Files:**
- Create: `engine.py`

- [ ] **Step 1: 编写 engine.py**

```python
import subprocess
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import models

_executor = ThreadPoolExecutor(max_workers=10)
_lock = threading.Lock()


def submit_task(task_id):
    _executor.submit(_run_task, task_id)


def _run_task(task_id):
    task = models.get_task(task_id)
    if not task:
        return
    now = datetime.now(timezone.utc).isoformat()
    models.update_task(task_id, status='Running', updated_at=now)

    script = task['script_path']
    accept = task['accept_path']
    script_dir = os.path.dirname(os.path.abspath(script)) if os.path.dirname(script) else os.getcwd()

    if not os.path.isabs(accept):
        accept = os.path.join(script_dir, accept)

    log = ''
    try:
        proc = subprocess.Popen(
            script, shell=True, cwd=script_dir,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        stdout, _ = proc.communicate(timeout=3600)
        log = stdout or ''
        if proc.returncode == 0 and os.path.exists(accept):
            status = 'Success'
        else:
            status = 'Failed'
            if proc.returncode != 0:
                log += f'\n[Exit code: {proc.returncode}]'
            if not os.path.exists(accept):
                log += f'\n[Accept file not found: {accept}]'
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        status = 'Failed'
        log = f'[Task timed out after 3600s]'
    except Exception as e:
        status = 'Failed'
        log = str(e)

    now = datetime.now(timezone.utc).isoformat()
    models.update_task(task_id, status=status, log=log, updated_at=now)


def shutdown():
    _executor.shutdown(wait=False, cancel_futures=True)
```

- [ ] **Step 2: 验证引擎基本逻辑**

```bash
python -c "
import models, engine
models.init_db()
# Create a task that runs 'echo hello && type nul > test_ok.txt'
tid = models.create_task('engine_test', '', 'cmd /c echo hello', 'test_ok.txt', 'user1', '芯片A')
engine.submit_task(tid)
import time; time.sleep(2)
t = models.get_task(tid)
print('Status:', t['status'], '| Log:', t['log'][:100])
models.delete_task(tid)
engine.shutdown()
"
```

---

### Task 5: Flask 应用骨架与认证

**Files:**
- Create: `app.py`

- [ ] **Step 1: 编写 app.py 骨架、secret key、login_required 装饰器、/login 路由**

```python
from flask import Flask, request, jsonify, session, redirect, url_for, render_template
from functools import wraps
import os
import models
import engine

app = Flask(__name__)
app.secret_key = os.urandom(24)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


@app.route('/login', methods=['GET', 'POST', 'DELETE'])
def login_page():
    if request.method == 'POST':
        data = request.get_json()
        if models.verify_password(data.get('password', '')):
            session['logged_in'] = True
            return jsonify({'ok': True})
        return jsonify({'error': 'Wrong password'}), 403
    if request.method == 'DELETE':
        session.pop('logged_in', None)
        return jsonify({'ok': True})
    if session.get('logged_in'):
        return redirect(url_for('index'))
    return render_template('index.html')


@app.route('/')
@login_required
def index():
    return render_template('index.html')
```

- [ ] **Step 2: 启动 Flask 验证路由可访问**

```bash
python -c "
import models; models.init_db()
from app import app
print('Flask app created, routes:')
for rule in app.url_map.iter_rules():
    print(' ', rule)
"
```

---

### Task 6: API 路由

**Files:**
- Modify: `app.py` — 追加以下路由

- [ ] **Step 1: 追加 /api/config, /api/tasks GET/POST, /api/tasks/<id>/copy, /api/tasks/<id> DELETE, /api/tasks/<id>/log, /api/poll**

```python
@app.route('/api/config')
@login_required
def api_config():
    return jsonify({'bindings': models.get_bindings()})


@app.route('/api/tasks', methods=['GET', 'POST'])
@login_required
def api_tasks():
    if request.method == 'POST':
        data = request.get_json()
        if not data.get('name') or not data.get('script_path') or not data.get('accept_path'):
            return jsonify({'error': 'Missing required fields'}), 400
        task_id = models.create_task(
            name=data['name'],
            detail=data.get('detail', ''),
            script_path=data['script_path'],
            accept_path=data['accept_path'],
            assignee=data.get('assignee', ''),
            design=data.get('design', ''),
        )
        engine.submit_task(task_id)
        return jsonify({'id': task_id}), 201

    status = request.args.get('status')
    tasks = models.get_tasks(status=status)
    return jsonify({'tasks': tasks})


@app.route('/api/tasks/<int:task_id>/copy', methods=['POST'])
@login_required
def api_copy_task(task_id):
    original = models.get_task(task_id)
    if not original:
        return jsonify({'error': 'Task not found'}), 404
    new_id = models.create_task(
        name=original['name'] + ' (copy)',
        detail=original['detail'],
        script_path=original['script_path'],
        accept_path=original['accept_path'],
        assignee=original['assignee'],
        design=original['design'],
    )
    engine.submit_task(new_id)
    return jsonify({'id': new_id}), 201


@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
@login_required
def api_delete_task(task_id):
    models.delete_task(task_id)
    return jsonify({'ok': True})


@app.route('/api/tasks/<int:task_id>/log')
@login_required
def api_task_log(task_id):
    task = models.get_task(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify({'log': task['log']})


@app.route('/api/poll')
@login_required
def api_poll():
    since = request.args.get('since', '')
    if since:
        tasks = models.get_tasks_since(since)
    else:
        tasks = models.get_tasks()
    return jsonify({'tasks': tasks, 'counts': models.get_status_counts()})
```

- [ ] **Step 2: 验证 API — 用 curl 测试创建和查询**

```bash
# Start Flask in background
python -c "
import models; models.init_db()
from app import app
app.run(port=5000, debug=False)
" &
sleep 2
# Test login
curl -s -X POST http://localhost:5000/login -H 'Content-Type: application/json' -d '{"password":"admin123"}' -c /tmp/cookies.txt
# Test create
curl -s -X POST http://localhost:5000/api/tasks -H 'Content-Type: application/json' -d '{"name":"api_test","script_path":"cmd /c echo ok","accept_path":"nope.txt","assignee":"user1","design":"芯片A"}' -b /tmp/cookies.txt
# Test list
curl -s http://localhost:5000/api/tasks -b /tmp/cookies.txt
# Cleanup
kill %1 2>/dev/null
```

---

### Task 7: 前端 — 登录与骨架

**Files:**
- Create: `templates/index.html`

- [ ] **Step 1: 编写 HTML 骨架、CSS 变量、登录表单、dashboard 容器**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Task Board</title>
<style>
:root {
  --bg: #f0f2f5;
  --card: #fff;
  --text: #1a1a1a;
  --muted: #888;
  --border: #e0e0e0;
  --pending: #ff9800;
  --running: #2196f3;
  --success: #4caf50;
  --failed: #f44336;
  --radius: 6px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
.card { background: var(--card); border-radius: var(--radius); box-shadow: 0 2px 8px rgba(0,0,0,0.08); padding: 32px; width: 100%; max-width: 420px; }
.card.wide { max-width: 1100px; }
h1 { font-size: 20px; margin-bottom: 4px; }
.sub { color: var(--muted); font-size: 13px; margin-bottom: 20px; }
input, textarea, select { width: 100%; padding: 8px 10px; border: 1px solid var(--border); border-radius: var(--radius); font-size: 13px; margin-bottom: 10px; }
textarea { resize: vertical; min-height: 60px; }
.btn { display: inline-block; padding: 8px 18px; border: none; border-radius: var(--radius); font-size: 13px; cursor: pointer; }
.btn-primary { background: #1677ff; color: #fff; }
.btn-primary:hover { background: #4096ff; }
.btn-sm { padding: 4px 10px; font-size: 12px; }
.btn-danger { background: #fff; color: var(--failed); border: 1px solid var(--failed); }
.btn-danger:hover { background: #fff1f0; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--border); }
th { background: #fafafa; font-weight: 600; color: var(--muted); }
.badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.badge-Pending { background: #fff3e0; color: var(--pending); }
.badge-Running { background: #e3f2fd; color: var(--running); }
.badge-Success { background: #e8f5e9; color: var(--success); }
.badge-Failed { background: #ffebee; color: var(--failed); }
.stats { display: flex; gap: 16px; margin-bottom: 16px; font-size: 13px; }
.stat { display: flex; align-items: center; gap: 4px; }
.hidden { display: none !important; }
.form-row { display: flex; gap: 10px; }
.form-row > * { flex: 1; }
.design-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.design-chip { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; border: 1px solid var(--border); border-radius: 14px; font-size: 12px; cursor: pointer; user-select: none; }
.design-chip.active { background: #e6f4ff; border-color: #1677ff; color: #1677ff; }
.topbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.log-modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: center; z-index: 100; }
.log-modal-content { background: #fff; border-radius: var(--radius); padding: 24px; width: 90%; max-width: 700px; max-height: 80vh; overflow: auto; }
.log-modal pre { background: #1a1a1a; color: #0f0; padding: 16px; border-radius: var(--radius); font-size: 12px; overflow-x: auto; white-space: pre-wrap; word-break: break-all; }
</style>
</head>
<body>

<!-- Login View -->
<div id="loginView" class="card">
  <h1>Task Board</h1>
  <p class="sub">请输入密码以继续</p>
  <input type="password" id="passwordInput" placeholder="Password" onkeydown="if(event.key==='Enter')login()">
  <button class="btn btn-primary" onclick="login()" style="width:100%">登录</button>
  <p id="loginError" style="color:var(--failed);font-size:12px;margin-top:8px;"></p>
</div>

<!-- Dashboard View -->
<div id="dashView" class="card wide hidden">
  <div class="topbar">
    <h1>Task Board</h1>
    <button class="btn btn-sm" onclick="logout()">退出</button>
  </div>

  <div class="stats">
    <span class="stat">⏳ Pending: <strong id="cntPending">0</strong></span>
    <span class="stat">🔄 Running: <strong id="cntRunning">0</strong></span>
    <span class="stat">✅ Success: <strong id="cntSuccess">0</strong></span>
    <span class="stat">❌ Failed: <strong id="cntFailed">0</strong></span>
  </div>

  <div class="form-row">
    <input type="text" id="taskName" placeholder="任务名 *">
    <input type="text" id="scriptPath" placeholder="脚本路径 *">
  </div>
  <div class="form-row">
    <input type="text" id="acceptPath" placeholder="验收文件路径 *">
    <input type="text" id="assignee" placeholder="执行者 (自动匹配)" readonly style="background:#f5f5f5;">
  </div>
  <textarea id="taskDetail" placeholder="任务详情 (可选)"></textarea>
  <div class="design-chips" id="designChips"></div>
  <div style="margin-bottom:16px;">
    <button class="btn btn-primary" onclick="createTask()">发布任务</button>
    <span id="formError" style="color:var(--failed);font-size:12px;margin-left:10px;"></span>
  </div>

  <table>
    <thead>
      <tr><th>ID</th><th>任务名</th><th>执行者</th><th>Design</th><th>状态</th><th>操作</th></tr>
    </thead>
    <tbody id="taskTable"></tbody>
  </table>
</div>

<!-- Log Modal -->
<div id="logModal" class="log-modal hidden" onclick="if(event.target===this)closeLog()">
  <div class="log-modal-content">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
      <h3 id="logTitle">日志</h3>
      <button class="btn btn-sm" onclick="closeLog()">关闭</button>
    </div>
    <pre id="logContent"></pre>
  </div>
</div>

<script>
// JS will be added in next task
</script>

</body>
</html>
```

---

### Task 8: 前端 — JavaScript 逻辑

**Files:**
- Modify: `templates/index.html` — 替换 `<script>` 块

- [ ] **Step 1: 编写 JS — 登录、绑定加载、表单、任务表格、轮询、日志弹窗**

```javascript
let pollTimer = null;
let lastSince = '';
let bindings = [];

// --- Login ---
async function login() {
  const pw = document.getElementById('passwordInput').value;
  const res = await fetch('/login', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({password: pw})
  });
  if (res.ok) {
    document.getElementById('loginView').classList.add('hidden');
    document.getElementById('dashView').classList.remove('hidden');
    initDashboard();
  } else {
    document.getElementById('loginError').textContent = '密码错误';
  }
}

async function logout() {
  await fetch('/login', {method: 'DELETE'});
  clearInterval(pollTimer);
  document.getElementById('loginView').classList.remove('hidden');
  document.getElementById('dashView').classList.add('hidden');
  document.getElementById('passwordInput').value = '';
  document.getElementById('loginError').textContent = '';
}

// --- Init ---
async function initDashboard() {
  await loadBindings();
  await refreshAll();
  pollTimer = setInterval(poll, 3000);
}

async function loadBindings() {
  const res = await fetch('/api/config');
  const data = await res.json();
  bindings = data.bindings;
  const container = document.getElementById('designChips');
  const allDesigns = [...new Set(bindings.flatMap(b => b.designs))];
  container.innerHTML = allDesigns.map(d =>
    `<span class="design-chip" data-design="${d}" onclick="toggleDesign(this)">${d}</span>`
  ).join('');
}

// --- Design multi-select + assignee auto-fill ---
function toggleDesign(el) {
  el.classList.toggle('active');
  autoFillAssignee();
}

function autoFillAssignee() {
  const selected = [...document.querySelectorAll('.design-chip.active')].map(el => el.dataset.design);
  if (selected.length === 0) {
    document.getElementById('assignee').value = '';
    return;
  }
  const candidates = bindings.filter(b => selected.every(d => b.designs.includes(d)));
  const assignees = [...new Set(candidates.map(b => b.assignee))];
  document.getElementById('assignee').value = assignees.join(', ');
}

// --- CRUD ---
async function createTask() {
  const name = document.getElementById('taskName').value.trim();
  const scriptPath = document.getElementById('scriptPath').value.trim();
  const acceptPath = document.getElementById('acceptPath').value.trim();
  if (!name || !scriptPath || !acceptPath) {
    document.getElementById('formError').textContent = '任务名、脚本路径、验收路径为必填';
    return;
  }
  const design = [...document.querySelectorAll('.design-chip.active')].map(el => el.dataset.design).join(',');
  const res = await fetch('/api/tasks', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      name, detail: document.getElementById('taskDetail').value,
      script_path: scriptPath, accept_path: acceptPath,
      assignee: document.getElementById('assignee').value,
      design: design
    })
  });
  if (res.ok) {
    document.getElementById('taskName').value = '';
    document.getElementById('taskDetail').value = '';
    document.getElementById('scriptPath').value = '';
    document.getElementById('acceptPath').value = '';
    document.getElementById('formError').textContent = '';
    document.querySelectorAll('.design-chip.active').forEach(el => el.classList.remove('active'));
    document.getElementById('assignee').value = '';
    await refreshAll();
  } else {
    const err = await res.json();
    document.getElementById('formError').textContent = err.error || '创建失败';
  }
}

async function copyTask(id) {
  const res = await fetch(`/api/tasks/${id}/copy`, {method: 'POST'});
  if (res.ok) await refreshAll();
}

async function deleteTask(id) {
  if (!confirm('确认删除任务 #' + id + '?')) return;
  await fetch(`/api/tasks/${id}`, {method: 'DELETE'});
  await refreshAll();
}

async function viewLog(id, name) {
  const res = await fetch(`/api/tasks/${id}/log`);
  const data = await res.json();
  document.getElementById('logTitle').textContent = `#${id} ${name}`;
  document.getElementById('logContent').textContent = data.log || '(empty)';
  document.getElementById('logModal').classList.remove('hidden');
}

function closeLog() {
  document.getElementById('logModal').classList.add('hidden');
}

// --- Polling ---
async function poll() {
  const res = await fetch(`/api/poll?since=${encodeURIComponent(lastSince)}`);
  const data = await res.json();
  if (data.tasks && data.tasks.length > 0) {
    updateTableRows(data.tasks);
    lastSince = data.tasks[0].updated_at;
  }
  if (data.counts) {
    document.getElementById('cntPending').textContent = data.counts.Pending;
    document.getElementById('cntRunning').textContent = data.counts.Running;
    document.getElementById('cntSuccess').textContent = data.counts.Success;
    document.getElementById('cntFailed').textContent = data.counts.Failed;
  }
}

async function refreshAll() {
  const res = await fetch('/api/poll');
  const data = await res.json();
  if (data.tasks) {
    renderTable(data.tasks);
    if (data.tasks.length > 0) lastSince = data.tasks[0].updated_at;
  }
  if (data.counts) {
    document.getElementById('cntPending').textContent = data.counts.Pending;
    document.getElementById('cntRunning').textContent = data.counts.Running;
    document.getElementById('cntSuccess').textContent = data.counts.Success;
    document.getElementById('cntFailed').textContent = data.counts.Failed;
  }
}

function renderTable(tasks) {
  document.getElementById('taskTable').innerHTML = tasks.map(t => rowHTML(t)).join('');
}

function updateTableRows(tasks) {
  for (const t of tasks) {
    const existing = document.getElementById(`row-${t.id}`);
    const html = rowHTML(t);
    if (existing) {
      existing.outerHTML = html;
    } else {
      document.getElementById('taskTable').insertAdjacentHTML('afterbegin', html);
    }
  }
}

function rowHTML(t) {
  return `<tr id="row-${t.id}">
    <td>${t.id}</td>
    <td title="${esc(t.detail)}">${esc(t.name)}</td>
    <td>${esc(t.assignee)}</td>
    <td>${esc(t.design)}</td>
    <td><span class="badge badge-${t.status}">${t.status}</span></td>
    <td>
      <button class="btn btn-sm" onclick="viewLog(${t.id},'${esc(t.name)}')">日志</button>
      <button class="btn btn-sm" onclick="copyTask(${t.id})">复制</button>
      <button class="btn btn-sm btn-danger" onclick="deleteTask(${t.id})">删除</button>
    </td>
  </tr>`;
}

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
```

---

### Task 9: Tkinter 托盘启动器

**Files:**
- Create: `tray.py`

- [ ] **Step 1: 编写 tray.py**

```python
import threading
import webbrowser
import sys
import os

os.environ['FLASK_RUN_PORT'] = '5000'

import tkinter as tk
import models
from app import app


def run_flask():
    models.init_db()
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)


def open_browser():
    webbrowser.open('http://localhost:5000')


def on_exit():
    import engine
    engine.shutdown()
    root.destroy()
    os._exit(0)


if __name__ == '__main__':
    models.init_db()
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    root = tk.Tk()
    root.title('Task Board')
    root.geometry('1x1+9999+9999')
    root.withdraw()

    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label='Open Browser', command=open_browser)
    menu.add_separator()
    menu.add_command(label='Exit', command=on_exit)

    def show_menu(e):
        menu.tk_popup(e.x_root, e.y_root)

    # Simple system tray via a tiny toplevel + bind
    root.bind('<Button-3>', show_menu)
    root.protocol('WM_DELETE_WINDOW', on_exit)

    # Windows real tray via Shell_NotifyIcon
    if sys.platform == 'win32':
        try:
            import ctypes
            from ctypes import wintypes
            GUID = [0x0D96A545, 0x22C1, 0x43D7, [0xB4,0x1B,0x7F,0x6C,0x7B,0x9D,0xE1,0x0F]]

            class NOTIFYICONDATA(ctypes.Structure):
                _fields_ = [
                    ('cbSize', wintypes.DWORD),
                    ('hWnd', wintypes.HWND),
                    ('uID', wintypes.UINT),
                    ('uFlags', wintypes.UINT),
                    ('uCallbackMessage', wintypes.UINT),
                    ('hIcon', wintypes.HICON),
                    ('szTip', ctypes.c_wchar * 128),
                    ('dwState', wintypes.DWORD),
                    ('dwStateMask', wintypes.DWORD),
                    ('szInfo', ctypes.c_wchar * 256),
                    ('uVersion', wintypes.UINT),
                    ('szInfoTitle', ctypes.c_wchar * 64),
                    ('dwInfoFlags', wintypes.DWORD),
                    ('guidItem', ctypes.c_byte * 16),
                    ('hBalloonIcon', wintypes.HICON),
                ]

            WM_TASKBAR = 0x8000 + 1
            NIM_ADD = 0
            NIM_DELETE = 2
            NIF_MESSAGE = 1
            NIF_TIP = 4

            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            nid = NOTIFYICONDATA()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
            nid.hWnd = hwnd
            nid.uID = 1
            nid.uFlags = NIF_MESSAGE | NIF_TIP
            nid.uCallbackMessage = WM_TASKBAR
            nid.szTip = 'Task Board'
            ctypes.windll.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

            root.protocol('WM_DELETE_WINDOW', root.withdraw)

            def win_proc(msg, wParam, lParam):
                if msg == WM_TASKBAR and lParam == 0x205:
                    menu.tk_popup(root.winfo_pointerx(), root.winfo_pointery())
                return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wParam, lParam)

            root.after(100, lambda: None)
        except Exception:
            pass

    print('Task Board running at http://localhost:5000')
    open_browser()
    root.mainloop()
```

- [ ] **Step 2: 验证托盘应用启动**

```bash
# Quick syntax check — full launch requires display
python -c "import ast; ast.parse(open('tray.py').read()); print('Syntax OK')"
```

---

### Task 10: 集成测试

**Files:**
- Create: `test_integration.py`

- [ ] **Step 1: 编写集成测试脚本**

```python
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import models
import engine
from app import app


def test_full_flow():
    models.init_db()
    client = app.test_client()

    # 1. Unauthorized access
    rv = client.get('/api/tasks')
    assert rv.status_code == 401, f'Expected 401 got {rv.status_code}'

    # 2. Login with wrong password
    rv = client.post('/login', json={'password': 'wrong'})
    assert rv.status_code == 403

    # 3. Login with correct password
    rv = client.post('/login', json={'password': 'admin123'})
    assert rv.status_code == 200

    # 4. Get bindings
    rv = client.get('/api/config')
    assert rv.status_code == 200
    assert len(rv.get_json()['bindings']) == 2

    # 5. Create task
    rv = client.post('/api/tasks', json={
        'name': 'integration_test',
        'detail': 'test detail',
        'script_path': 'cmd /c echo hello',
        'accept_path': 'does_not_exist.txt',
        'assignee': 'user1',
        'design': '芯片A,芯片B',
    })
    assert rv.status_code == 201
    task_id = rv.get_json()['id']

    # 6. Get tasks
    rv = client.get('/api/tasks')
    assert rv.status_code == 200
    tasks = rv.get_json()['tasks']
    assert len(tasks) >= 1

    # 7. Wait for execution (short)
    import time; time.sleep(3)
    rv = client.get(f'/api/tasks/{task_id}/log')
    assert rv.status_code == 200
    log_data = rv.get_json()
    assert 'hello' in log_data['log'] or 'Failed' in str(log_data)

    # 8. Copy task
    rv = client.post(f'/api/tasks/{task_id}/copy')
    assert rv.status_code == 201
    copy_id = rv.get_json()['id']
    time.sleep(2)

    # 9. Delete tasks
    rv = client.delete(f'/api/tasks/{task_id}')
    assert rv.status_code == 200
    rv = client.delete(f'/api/tasks/{copy_id}')
    assert rv.status_code == 200

    # 10. Poll with since
    rv = client.get('/api/poll?since=2020-01-01T00:00:00')
    assert rv.status_code == 200
    assert 'counts' in rv.get_json()

    engine.shutdown()
    print('All integration tests passed!')


if __name__ == '__main__':
    test_full_flow()
```

- [ ] **Step 2: 运行集成测试**

```bash
python test_integration.py
```

---

### Task 11: 最终验证与清理

- [ ] **Step 1: 确认所有文件存在**

```bash
ls -la models.py engine.py app.py tray.py config.json requirements.txt templates/index.html test_integration.py
```

- [ ] **Step 2: 运行集成测试确认全部通过**

```bash
python test_integration.py
```

- [ ] **Step 3: 清理测试残留**

```bash
rm -f tasks.db test_ok.txt
```
