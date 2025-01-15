"""Web应用模块，用于显示爬虫状态和日志"""

import os
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, flash, redirect, url_for

from .. import config
from ..crawler.auth import CookieManager
from ..crawler.run_history import RunLogger
from ..crawler.scheduler import Scheduler
from .db import db
from ..utils import LogManager

# 加载 .env 文件
load_dotenv()

app = Flask(__name__)

# 设置Web应用日志
logger = LogManager.setup_logger("web")

# 添加模板函数
app.jinja_env.globals.update(max=max, min=min)

# 创建全局的调度器实例
scheduler = Scheduler()

# 创建全局的CookieManager实例
cookie_manager = CookieManager()


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
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # 获取搜索关键词
        query = request.args.get('q', '').strip()
        
        if query:
            # 如果有搜索关键词，使用搜索功能
            items, total = db.search_weibos(query, page, per_page)
        else:
            # 否则获取所有收藏
            items, total = db.get_favorites(page, per_page)
            
        total_pages = (total + per_page - 1) // per_page
        
        return render_template(
            'favorites.html',
            items=items,
            total=total,
            page=page,
            total_pages=total_pages,
            query=query
        )
    except Exception as e:
        logger.error(f"获取收藏列表失败: {e}")
        flash('获取收藏列表失败', 'error')
        return render_template('favorites.html', items=[], total=0, page=1, total_pages=1)


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


@app.route("/api/cookie/status")
def get_cookie_status():
    """获取Cookie状态"""
    return jsonify(cookie_manager.get_status())


@app.route('/weibo/<weibo_id>')
def weibo_detail(weibo_id):
    """微博详情页面"""
    try:
        # 从数据库获取微博信息
        weibo = db.get_weibo_by_id(weibo_id)
        if not weibo:
            flash('未找到该微博', 'error')
            return redirect(url_for('favorites'))
            
        return render_template('weibo_detail.html', item=weibo)
    except Exception as e:
        logger.error(f"获取微博详情失败: {e}")
        flash('获取微博详情失败', 'error')
        return redirect(url_for('favorites'))


def run_web():
    """运行Web应用"""
    # 确保日志和数据目录存在
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    os.makedirs(config.DATA_DIR, exist_ok=True)

    # cookie有效性检验
    valid, error = cookie_manager.check_validity()
    if not valid:
        logger.warning(f"Cookie无效: {error}")
    else:
        logger.info("Cookie验证成功")

        # 自动启动调度器
        if not scheduler.running:
            # scheduler.start(cookie_manager)
            logger.info("调度器已自动启动")

    # 运行Flask应用
    app.run(host="0.0.0.0", port=5001, debug=True)


if __name__ == "__main__":
    run_web()
