# 暂时强制指定为x64架构
# https://github.com/wangfenjin/simple/issues/154
FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY src /app/src
COPY scripts /app/scripts
COPY setup.py /app/
COPY README.md /app/

# 安装 Python 依赖
RUN pip install -e .

# 下载并安装 SQLite 扩展
RUN mkdir -p libs\
    && ARCH=$(uname -m) \
    && if [ "$ARCH" = "aarch64" ]; then \
        SIMPLE_PKG="libsimple-aarch64-linux-gnu-gcc.zip"; \
    elif [ "$ARCH" = "x86_64" ]; then \
        SIMPLE_PKG="libsimple-linux-ubuntu-latest.zip"; \
    else \
        echo "Error: Unsupported architecture: $ARCH (only aarch64 and x86_64 are supported)" && exit 1; \
    fi \
    && echo "Downloading $SIMPLE_PKG for architecture $ARCH..." \
    && wget "https://github.com/wangfenjin/simple/releases/download/v0.4.0/$SIMPLE_PKG" \
    && unzip "$SIMPLE_PKG" \
    && cp -r "${SIMPLE_PKG%.*}"/* libs/ \
    && chmod +x libs/libsimple.so \
    && rm -rf "$SIMPLE_PKG" "${SIMPLE_PKG%.*}"

# 设置环境变量
ENV LD_LIBRARY_PATH=/app:$LD_LIBRARY_PATH

# 启动 worker
CMD ["python", "scripts/run_worker.py"]
