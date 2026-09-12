# --- 构建阶段 ---
FROM node:20-bookworm-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html vite.config.ts tsconfig.json playwright.config.ts ./
COPY src ./src
COPY e2e ./e2e
RUN npm run build

# --- 运行阶段:nginx 托管静态资源并反向代理 /api ---
FROM nginx:1.27-bookworm

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
