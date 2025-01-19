FROM python:3.11-slim

# 安装 rq-dashboard
RUN pip install rq-dashboard

EXPOSE 9181

# 启动 dashboard
CMD ["rq-dashboard", "--bind", "0.0.0.0", "--port", "9181"]
