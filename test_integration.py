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

    # 5c. Verify task_items were auto-created for each design
    rv = client.get(f'/api/tasks/{task_id}/items')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'task' in data
    assert 'items' in data
    items = data['items']
    assert len(items) == 2  # 芯片A,芯片B
    designs_in_items = {it['design'] for it in items}
    assert designs_in_items == {'芯片A', '芯片B'}
    for it in items:
        assert it['status'] == 'Running'
        assert it['user'] == 'zhangsan'

    # 5d. No items for task without design
    rv = client.get(f'/api/tasks/{noscript_id}/items')
    assert rv.status_code == 200
    assert len(rv.get_json()['items']) == 1  # 芯片D
    assert rv.get_json()['items'][0]['design'] == '芯片D'

    # 5e. Update item status — chipA Success, chipB Failed
    item_a = [i for i in items if i['design'] == '芯片A'][0]
    item_b = [i for i in items if i['design'] == '芯片B'][0]
    rv = client.put(f'/api/tasks/{task_id}/items', json={
        'item_id': item_a['id'], 'status': 'Success'
    })
    assert rv.status_code == 200

    rv = client.put(f'/api/tasks/{task_id}/items', json={
        'item_id': item_b['id'], 'status': 'Failed'
    })
    assert rv.status_code == 200

    # 5f. Verify task status recalculated to Failed (one item Failed)
    rv = client.get('/api/tasks')
    tasks_after = rv.get_json()['tasks']
    t_updated = [x for x in tasks_after if x['id'] == task_id][0]
    assert t_updated['status'] == 'Failed'

    # 5g. Update item notes
    rv = client.put(f'/api/tasks/{task_id}/items', json={
        'item_id': item_a['id'], 'notes': 'Passed all checks'
    })
    assert rv.status_code == 200
    rv = client.get(f'/api/tasks/{task_id}/items')
    item_a_updated = [i for i in rv.get_json()['items'] if i['id'] == item_a['id']][0]
    assert item_a_updated['notes'] == 'Passed all checks'

    # 6. Get tasks — verify default status is Running
    rv = client.get('/api/tasks')
    assert rv.status_code == 200
    tasks = rv.get_json()['tasks']
    assert len(tasks) >= 2
    t = [x for x in tasks if x['id'] == task_id][0]
    assert t['user'] == 'zhangsan'
    assert t['start_date'] == '2026-05-01'
    assert t['status'] in ('Running', 'Success', 'Failed')

    # 7. Update task status manually
    rv = client.put(f'/api/tasks/{task_id}', json={'status': 'Running'})
    assert rv.status_code == 200
    t = models.get_task(task_id)
    assert t['status'] == 'Running'

    # 7b. Verify per-design user lookup (zhangsan handles both 芯片A and 芯片B)
    rv = client.get(f'/api/tasks/{task_id}/items')
    items_check = rv.get_json()['items']
    for it in items_check:
        assert it['user'] == 'zhangsan', f'Expected zhangsan for {it["design"]}, got {it["user"]}'

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
    print('All integration tests passed!')


if __name__ == '__main__':
    test_full_flow()
