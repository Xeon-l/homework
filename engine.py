import subprocess
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import models

_executor = ThreadPoolExecutor(max_workers=10)


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
    if not os.path.isdir(script_dir):
        script_dir = os.getcwd()

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
