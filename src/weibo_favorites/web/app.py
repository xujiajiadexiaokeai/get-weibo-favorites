"""Web application for Weibo Favorites"""

import os
from datetime import datetime
from flask import Flask, render_template, jsonify, request
import sqlite3

from .. import config
from ..utils import setup_logger

# 设置Web应用日志
web_logger = setup_logger(
    "web",
    log_file=config.LOGS_DIR / "web.log",
    log_level=config.LOG_LEVEL
)

app = Flask(__name__)

# 添加模板函数
app.jinja_env.globals.update(max=max, min=min)

def get_db():
    """获取数据库连接"""
    db = sqlite3.connect(config.DATABASE_FILE)
    db.row_factory = sqlite3.Row
    return db

@app.route('/')
def index():
    """首页 - 显示爬虫状态和日志"""
    # 读取爬虫状态
    try:
        with open(config.CRAWLER_STATE_FILE, 'r') as f:
            crawler_state = f.read()
    except:
        crawler_state = "未找到爬虫状态文件"
    
    # 读取最新的日志
    try:
        with open(config.LOG_FILE, 'r') as f:
            logs = f.readlines()[-50:]  # 最新的50行日志
    except:
        logs = ["未找到日志文件"]
    
    return render_template('index.html',
                         crawler_state=crawler_state,
                         logs=logs,
                         current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/favorites')
def favorites():
    """收藏列表页面"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    db = get_db()
    cursor = db.cursor()
    
    # 获取总数
    total = cursor.execute('SELECT COUNT(*) FROM weibo_favorites').fetchone()[0]
    
    # TODO: 修改created_at字段格式，然后优化查询
    # 获取分页数据
    offset = (page - 1) * per_page
    cursor.execute('''
        SELECT * FROM weibo_favorites 
        ORDER BY strftime('%Y-%m-%d %H:%M:%S', 
            REPLACE(
                REPLACE(created_at, ' +0800', ''),
                'Sun ', ''
            )
        ) DESC 
        LIMIT ? OFFSET ?
    ''', (per_page, offset))
    items = cursor.fetchall()
    
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('favorites.html',
                         items=items,
                         page=page,
                         total_pages=total_pages,
                         total=total)

@app.route('/api/logs')
def get_logs():
    """获取最新日志的API"""
    try:
        with open(config.LOG_FILE, 'r') as f:
            logs = f.readlines()[-50:]
        return jsonify({'logs': logs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run_web():
    """运行Web应用"""
    # 确保日志目录存在
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 确保数据库文件所在目录存在
    config.DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    web_logger.info("启动Web应用")
    app.run(host='0.0.0.0', port=5001, debug=True)

if __name__ == '__main__':
    run_web()
