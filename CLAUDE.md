# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述
内网任务发布与监控系统 — 轻量级 Web 应用，用于发布、执行和监控本地脚本任务。

## 技术栈
- **后端**: Python 3 + Tkinter（不支持 PyQt6）
- **前端**: 单页 HTML（内嵌于 Tkinter WebView 或独立 HTTP 服务）

## 运行方式
```bash
# 安装依赖
pip install -r requirements.txt

# 启动应用
python main.py
```

## 架构
- `main.py` — 应用入口，启动 Tkinter 主窗口和 HTTP 服务
- `models.py` — SQLite 数据模型（Task 表）
- `engine.py` — 任务执行引擎（subprocess 调用脚本、状态机管理、验收检查）
- `routes.py` — HTTP API 路由（发布任务、查询状态、查看日志）
- `templates/index.html` — 前端单页看板
- `config.json` — 执行者与 design 的绑定关系配置

## 数据库模型
`Task` 表字段：id, name, detail, script_path, accept_path, assignee, status(Pending/Running/Success/Failed), log, created_at, updated_at

## 核心逻辑
1. 发布任务 → 写入 DB (status=Pending) → 触发异步执行
2. 执行器通过 subprocess 运行脚本路径，捕获 stdout/stderr 写入 log
3. 执行完成后检查验收文件路径是否存在 → 更新 status 为 Success 或 Failed
