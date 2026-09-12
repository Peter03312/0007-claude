# 一次性验收服务 verify:
# 在同一容器内真实启动 FastAPI 与 nginx 托管的 React 构建产物,
# 然后依次执行 pytest、Vitest、Playwright(Chromium),全部通过才退出 0。
#
# 基础镜像自带 Python 3.12、pip;再安装 Node.js 20 与浏览器依赖。
FROM mcr.microsoft.com/playwright/python:v1.49.1-noble

ENV DEBIAN_FRONTEND=noninteractive \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# 安装 Node.js 20
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg nginx \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work

# ---- 后端依赖(pytest 用 httpx + TestClient,无需网络服务) ----
COPY backend/requirements-dev.txt /tmp/requirements-dev.txt
RUN pip install --no-cache-dir -r /tmp/requirements-dev.txt

# ---- 前端依赖(含 @playwright/test;浏览器二进制基础镜像已预装) ----
COPY frontend/package.json frontend/package-lock.json /work/frontend/
RUN cd /work/frontend \
    && npm ci \
    && npx playwright install chromium

# ---- 拷贝全部源码 ----
COPY backend /work/backend
COPY frontend /work/frontend
COPY verify/entrypoint.sh /work/entrypoint.sh
RUN chmod +x /work/entrypoint.sh

EXPOSE 80

CMD ["/work/entrypoint.sh"]
