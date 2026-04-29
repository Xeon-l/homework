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

    # Windows tray via Shell_NotifyIcon
    if sys.platform == 'win32':
        try:
            import ctypes
            from ctypes import wintypes

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
            pass  # fall back to hidden window mode

    print('Task Board running at http://localhost:5000')
    open_browser()
    root.mainloop()
