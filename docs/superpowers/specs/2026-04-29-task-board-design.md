# 内网任务发布与监控系统 — 设计规格

**日期**: 2026-04-29  
**状态**: 已确认  
**技术栈**: Python 3.12 + Flask + SQLite + Tkinter + HTML/CSS/JS

## 1. 目标

轻量级内网任务看板，发布脚本任务、监控执行状态、自动验收。整个项目目录复制到内网机器即可运行。

## 2. 架构

```
浏览器 (内网) ← HTTP → Flask (app.py) → models.py (SQLite)
                              ↓
                         engine.py (ThreadPoolExecutor + subprocess)
                              ↓
                         tray.py (Tkinter 系统托盘)
```

### 文件结构

```
homework/
├── app.py           # Flask 路由 + 入口
├── models.py        # SQLite 模型 + config 加载
├── engine.py        # 任务执行 + 状态管理
├── tray.py          # Tkinter 托盘启动器
├── config.json      # 执行者-Design 绑定 + 全局密码
├── requirements.txt # flask
└── templates/
    └── index.html   # 单页前端 (内嵌 CSS/JS)
```

### 关键设计决策

- 所有 HTML/CSS/JS 内嵌于模板文件中，无外部 CDN 引用，确保内网隔离环境可用
- Design 多选：发布任务时可同时关联多个 design 分类
- 执行者自动匹配：根据选中的 design 从 config.json 绑定关系中自动填充执行者

## 3. 数据模型

### Task 表 (SQLite)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK AUTOINCREMENT | 主键 |
| name | TEXT | NOT NULL | 任务名 |
| detail | TEXT | | 任务详情 |
| script_path | TEXT | NOT NULL | 脚本路径 |
| accept_path | TEXT | NOT NULL | 验收文件路径 |
| assignee | TEXT | NOT NULL | 执行者 (local id) |
| design | TEXT | NOT NULL | 关联 design，多选用逗号分隔 |
| status | TEXT | DEFAULT 'Pending' | Pending/Running/Success/Failed |
| log | TEXT | DEFAULT '' | stdout+stderr 合并输出 |
| created_at | TEXT | | ISO 8601 时间戳 |
| updated_at | TEXT | | ISO 8601 时间戳 |

### config.json

```json
{
  "bindings": [
    {"assignee": "user1", "designs": ["芯片A", "芯片B"]},
    {"assignee": "user2", "designs": ["芯片A"]}
  ],
  "password": "admin123"
}
```

## 4. API 路由

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 首页，需登录 |
| POST | `/login` | 密码验证，设置 session |
| GET | `/api/tasks` | 任务列表，支持 `?status=` 筛选 |
| POST | `/api/tasks` | 创建任务，自动触发执行 |
| POST | `/api/tasks/<id>/copy` | 克隆任务 (复用脚本/验收路径) |
| DELETE | `/api/tasks/<id>` | 删除任务 |
| GET | `/api/tasks/<id>/log` | 返回完整日志文本 |
| GET | `/api/config` | 返回 bindings 数组 (供前端下拉) |
| GET | `/api/poll` | 轻量轮询，传入 `?since=` ISO时间戳，返回此时间后有变更的任务 |

所有 `/api/*` 路由需 session 认证，未登录返回 401。

## 5. 执行引擎

### 状态机

```
Pending ──→ Running ──→ Success  (accept_path 文件存在)
                   └──→ Failed   (accept_path 不存在 或 脚本异常退出)
```

### 执行流程

1. 任务创建 → DB 写入 (status=Pending) → 提交到 ThreadPoolExecutor (max_workers=10)
2. Worker: 更新 status=Running → subprocess.Popen(script_path, shell=True)
3. 实时捕获 stdout/stderr，合并写入 log 字段
4. 脚本退出后检查 os.path.exists(accept_path) → 更新 status
5. 超时 (默认 3600s) 强制 kill → status=Failed

### 验收

- 脚本执行完毕后检查 `accept_path` 文件是否存在
- 绝对路径直接检查；相对路径相对于脚本所在目录 (cwd 设为脚本父目录)
- 存在 → Success，不存在 → Failed
- Design 名称不得含逗号 (逗号用作多选分隔符)

## 6. 前端

### 布局 (方案 A — 列表式)

- **顶部状态栏**: 登录状态、当前执行者、design 筛选
- **发布表单**: 任务名、任务详情(textarea)、脚本路径、验收路径、Design(多选)、执行者(自动匹配)
- **状态统计**: Pending / Running / Success / Failed 计数
- **任务表格**: ID、任务名、执行者、Design、状态(彩色标签)、日志按钮、复制按钮、删除按钮

### 行为

- 每 3 秒 GET `/api/poll` 增量刷新状态
- 发布按钮 → POST `/api/tasks` → 成功后清空表单、刷新表格
- 日志按钮 → 弹窗或新标签页展示完整日志
- 复制按钮 → POST `/api/tasks/<id>/copy` → 表单预填充，确认后创建

## 7. Tkinter 托盘

- 启动: 检查 DB → `threading.Thread` 启动 Flask → `iconify` 到系统托盘
- 右键菜单: 「打开浏览器」「退出」
- 退出: `atexit` 清理线程和子进程

## 8. 安全

- 全局密码存储在 config.json，经 `/login` 验证后设置 Flask session
- 所有页面和 API 通过 `@login_required` 装饰器保护
- 子进程在调用者的权限上下文中运行 (不额外降权或提权)

## 9. 部署

1. 复制 `homework/` 目录到内网机器
2. `pip install flask`
3. `python tray.py`
4. 浏览器打开 `http://localhost:5000`
