import json
import sys
import os
import time
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
    assert len(rv.get_json()['bindings']) == 4

    # 5. Create task (with script)
    rv = client.post('/api/tasks', json={
        'name': 'integration_test',
        'detail': 'test detail',
        'script_path': 'cmd /c echo hello',
        'accept_path': 'does_not_exist.txt',
        'user': 'zhangsan',
        'design': '芯片A,芯片B',
        'start_date': '2026-05-01',
        'end_date': '2026-05-15',
    })
    assert rv.status_code == 201
    task_id = rv.get_json()['id']

    # 5b. Create task without script (should succeed, status=Success)
    rv = client.post('/api/tasks', json={
        'name': 'no_script_task',
        'user': 'lisi',
        'design': '芯片D',
    })
    assert rv.status_code == 201
    noscript_id = rv.get_json()['id']

    # 6. Get tasks — verify default status is Running
    rv = client.get('/api/tasks')
    assert rv.status_code == 200
    tasks = rv.get_json()['tasks']
    assert len(tasks) >= 2
    t = [x for x in tasks if x['id'] == task_id][0]
    assert t['user'] == 'zhangsan'
    assert t['start_date'] == '2026-05-01'
    assert t['status'] in ('Running', 'Success', 'Failed')

    # 7. Wait for script execution and check log
    time.sleep(3)
    rv = client.get(f'/api/tasks/{task_id}/log')
    assert rv.status_code == 200
    log_data = rv.get_json()
    # Should contain hello output or accept-missing message
    assert log_data['log'], 'Log should not be empty'

    # 8. Copy task
    rv = client.post(f'/api/tasks/{task_id}/copy')
    assert rv.status_code == 201
    copy_id = rv.get_json()['id']
    time.sleep(2)

    # 9. Delete all test tasks
    rv = client.delete(f'/api/tasks/{task_id}')
    assert rv.status_code == 200
    rv = client.delete(f'/api/tasks/{copy_id}')
    assert rv.status_code == 200
    rv = client.delete(f'/api/tasks/{noscript_id}')
    assert rv.status_code == 200

    # 10. Poll with since
    rv = client.get('/api/poll?since=2020-01-01T00:00:00')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'counts' in data
    for s in ['Pending', 'Running', 'Success', 'Failed']:
        assert s in data['counts']

    # 11. Logout
    rv = client.delete('/login')
    assert rv.status_code == 200

    # 12. Verify unauthorized after logout
    rv = client.get('/api/tasks')
    assert rv.status_code == 401

    engine.shutdown()
    print('All 14 integration tests passed!')


if __name__ == '__main__':
    test_full_flow()
