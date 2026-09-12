#!/usr/bin/env bash
# 一次性验收:真实启动前后端 → pytest → Vitest → Playwright。
set -euo pipefail

BACKEND_DIR=/work/backend
FRONTEND_DIR=/work/frontend

echo "==> [1/5] 构建前端静态资源(React + TypeScript)"
cd "$FRONTEND_DIR"
npm run build

echo "==> [2/5] 启动 FastAPI(:8000)与 nginx(:80,反代 /api)"
( cd "$BACKEND_DIR" && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 ) &
API_PID=$!

# nginx 直接使用前端镜像里的同一份配置,root 指向本地构建产物
cat > /etc/nginx/conf.d/default.conf <<'NGINX'
server {
    listen 80;
    server_name _;
    root /work/frontend/dist;
    index index.html;
    location / { try_files $uri $uri/ /index.html; }
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }
}
NGINX
nginx

# 等待两个服务就绪
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/api/health >/dev/null \
     && curl -sf http://127.0.0.1:80/ >/dev/null; then
    echo "    服务已就绪"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "!! 服务启动超时"; exit 1
  fi
  sleep 1
done

STATUS=0

echo "==> [3/5] pytest(规则引擎 + API 边界)"
( cd "$BACKEND_DIR" && python -m pytest -q ) || STATUS=1

echo "==> [4/5] Vitest(前端 API 封装与页面交互)"
( cd "$FRONTEND_DIR" && npx vitest run ) || STATUS=1

echo "==> [5/5] Playwright(真实浏览器端到端联调)"
( cd "$FRONTEND_DIR" \
  && PLAYWRIGHT_BASE_URL=http://127.0.0.1:80 npx playwright test ) || STATUS=1

echo
if [ "$STATUS" -eq 0 ]; then
  echo "================ 验收通过:pytest / Vitest / Playwright 全部成功 ================"
else
  echo "================ 验收失败:见上方日志 ================"
fi

nginx -s stop || true
kill "$API_PID" 2>/dev/null || true
exit "$STATUS"
