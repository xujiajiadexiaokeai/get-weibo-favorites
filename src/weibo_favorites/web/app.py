"""Web应用模块，用于显示爬虫状态和日志"""

import os
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .. import config
from ..crawler.run_history import RunLogger
from ..crawler.scheduler import Scheduler
from ..utils import LogManager

app = Flask(__name__)
scheduler = Scheduler()

# 设置Web应用日志
logger = LogManager.setup_logger("web")

# 添加模板函数
app.jinja_env.globals.update(max=max, min=min)


@app.template_filter("datetime")
def format_datetime(value):
    """格式化日期时间"""
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return value


@app.template_filter("duration")
def format_duration(seconds):
    """格式化持续时间"""
    try:
        duration = timedelta(seconds=float(seconds))
        minutes, seconds = divmod(duration.seconds, 60)
        if minutes > 0:
            return f"{minutes}分{seconds}秒"
        return f"{seconds}秒"
    except:
        return "N/A"


def get_db():
    """获取数据库连接"""
    db = sqlite3.connect(config.DATABASE_FILE)
    db.row_factory = sqlite3.Row
    return db


@app.route("/")
def index():
    """首页 - 显示爬虫状态和日志"""
    # 读取爬虫状态
    try:
        with open(config.CRAWLER_STATE_FILE, "r") as f:
            crawler_state = f.read()
    except:
        crawler_state = "未找到爬虫状态文件"

    # 读取最新的日志
    try:
        with open(config.LOG_FILE, "r") as f:
            logs = f.readlines()[-20:]  # 最新的20行日志
    except:
        logs = ["未找到日志文件"]

    return render_template(
        "index.html",
        crawler_state=crawler_state,
        logs=logs,
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@app.route("/favorites")
def favorites():
    """收藏列表页面"""
    page = request.args.get("page", 1, type=int)
    per_page = 20

    db = get_db()
    cursor = db.cursor()

    # 获取总数
    total = cursor.execute("SELECT COUNT(*) FROM weibo_favorites").fetchone()[0]

    # TODO: 修改created_at字段格式，然后优化查询
    # 获取分页数据
    offset = (page - 1) * per_page
    cursor.execute(
        """
        SELECT 
            id, created_at, url, user_name, user_id, is_long_text, text, text_html, source, links FROM weibo_favorites 
        ORDER BY 
            created_at DESC 
        LIMIT ? OFFSET ?
    """,
        (per_page, offset),
    )
    items = cursor.fetchall()

    total_pages = (total + per_page - 1) // per_page

    return render_template(
        "favorites.html", items=items, page=page, total_pages=total_pages, total=total
    )


@app.route("/runs")
def runs():
    """运行历史页面"""
    run_logger = RunLogger()
    runs = run_logger.get_all_runs()
    return render_template("runs.html", runs=runs)


@app.route("/api/runs/<run_id>/log")
def get_run_log(run_id):
    """获取运行日志

    Args:
        run_id: 运行ID

    Returns:
        运行日志内容
    """
    run_logger = RunLogger()
    log_path = run_logger.get_run_log_path(run_id)

    if not log_path.exists():
        return jsonify({"success": False, "error": "日志文件不存在"}), 404

    with open(log_path, "r", encoding="utf-8") as f:
        log = f.read()

    return jsonify({"success": True, "content": log})


@app.route("/api/logs")
def get_logs():
    """获取最新日志的API"""
    try:
        with open(config.LOG_FILE, "r") as f:
            logs = f.readlines()[-50:]
        return jsonify({"logs": logs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/scheduler/status")
def get_scheduler_status():
    """获取调度器状态"""
    return jsonify(scheduler.get_status())


@app.route("/api/scheduler/control", methods=["POST"])
def control_scheduler():
    """控制调度器"""
    action = request.json.get("action")
    if action == "start":
        if not scheduler.is_running():
            # 启动独立的调度器进程
            subprocess.Popen(
                ["python", "-m", "weibo_favorites.crawler.scheduler"],
                cwd=str(Path(config.PROJECT_ROOT)),
            )
        return jsonify({"status": "started"})
    elif action == "stop":
        scheduler.stop()
        return jsonify({"status": "stopped"})
    return jsonify({"error": "Invalid action"}), 400


def run_web():
    """运行Web应用"""
    # 确保日志目录存在
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # 确保数据库文件所在目录存在
    config.DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)

    logger.info("启动Web应用")
    app.run(host="0.0.0.0", port=5001, debug=True)


if __name__ == "__main__":
    run_web()
