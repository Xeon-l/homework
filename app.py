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


@app.route('/api/config')
@login_required
def api_config():
    return jsonify({'bindings': models.get_bindings()})


@app.route('/api/tasks', methods=['GET', 'POST'])
@login_required
def api_tasks():
    if request.method == 'POST':
        data = request.get_json()
        if not data.get('name'):
            return jsonify({'error': 'Task name is required'}), 400
        task_id = models.create_task(
            name=data['name'],
            detail=data.get('detail', ''),
            script_path=data.get('script_path', ''),
            accept_path=data.get('accept_path', ''),
            user=data.get('user', ''),
            design=data.get('design', ''),
            start_date=data.get('start_date', ''),
            end_date=data.get('end_date', ''),
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
        user=original['user'],
        design=original['design'],
        start_date=original.get('start_date', ''),
        end_date=original.get('end_date', ''),
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
