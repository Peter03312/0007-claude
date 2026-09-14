# 一次性验收服务 verify:
# 在同一容器内真实启动 FastAPI 与 nginx 托管的 React 构建产物,
# 然后依次执行 pytest、Vitest、Playwright(Chromium),全部通过才退出 0。
#
# 基础镜像(mcr.microsoft.com/playwright/python)基于 Ubuntu 24.04,
# 已预装 Python 3.12 与匹配版本的 Chromium 及全部系统库。
# 注意:该镜像系统 Python 受 PEP 668 保护,裸 pip install 会被拒绝,
# 因此后端依赖装进独立 venv(/opt/venv)。
FROM mcr.microsoft.com/playwright/python:v1.49.1-noble

ENV DEBIAN_FRONTEND=noninteractive \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PATH=/opt/venv/bin:$PATH

# 安装 Node.js 20、nginx,以及创建 venv 所需的 python3-venv
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg nginx python3-venv \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# 后端测试依赖装进 venv,规避 PEP 668(externally-managed-environment)。
# 注意:requirements-dev.txt 首行是 `-r requirements.txt`,
# 两个文件必须一起拷贝(且保名),否则 pip 无法解析 -r 引用,构建会在此中止。
RUN python3 -m venv /opt/venv
COPY backend/requirements.txt backend/requirements-dev.txt /tmp/
RUN /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements-dev.txt

WORKDIR /work

# 前端依赖(含 @playwright/test;Chromium 二进制基础镜像已预装)
COPY frontend/package.json frontend/package-lock.json /work/frontend/
RUN cd /work/frontend \
    && npm ci

# 拷贝全部源码
COPY backend /work/backend
COPY frontend /work/frontend
COPY verify/entrypoint.sh /work/entrypoint.sh
RUN chmod +x /work/entrypoint.sh

EXPOSE 80

CMD ["/work/entrypoint.sh"]
