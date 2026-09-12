# 危险品同位禁配核验台(空仓库全栈核验台)

临时卸货区会把等待转运的危险品并入空库位。本核验台让值班员在叉车落位前,
一次性录入「库位号 / 容器编号 / 类别 / 目标库位」,由后端规则引擎返回
**逐库位通过或失败**结论以及**规范化后的实际冲突容器对**。

技术栈:**Python 3.12 + FastAPI**(后端)、**React + TypeScript + Vite**(前端)、
**pytest / Vitest / Playwright**(测试)、**Docker Compose**(编排与一次性验收)。
前后端真实联调,无假接口、无固定响应。

---

## 一、核验规则(实现与本文件并排)

| 项目 | 规则 | 实现位置 |
| --- | --- | --- |
| 类别 | 仅允许 `A` 酸类、`B` 碱类、`O` 氧化剂、`F` 易燃品、`N` 中性 | `backend/app/rules.py: CATEGORIES` |
| 无向禁配对 | 恰为 **A-B、A-O、O-F**(正反序都算),其余所有组合兼容 | `backend/app/rules.py: FORBIDDEN_PAIRS / forbidden()` |
| 库位号 | **1 至 99 的整数** | `backend/app/rules.py: MIN_SLOT / MAX_SLOT` |
| 库位容量 | 每个库位最多 **4 个容器** | `backend/app/rules.py: MAX_CONTAINERS_PER_SLOT` |
| 容器编号 | **1 至 12 位大写字母或数字**(`^[A-Z0-9]{1,12}$`),**全批唯一**,每个容器只能出现一次 | `backend/app/rules.py: CONTAINER_RE` 及重复编号检查 |
| 冲突范围 | 只比对**同一库位**内的容器对,跨库位不冲突 | `backend/app/rules.py: verify()` 按库位分组 |
| 冲突对规范化 | 对内部按容器编号 **ASCII 字典序**排列 | `backend/app/rules.py: _pair_key()` |
| 结果排序 | 先按**库位号数值升序**,再按冲突对**首项、次项** ASCII 字典序 | `backend/app/rules.py: verify()` |
| 整批 422 | 重复编号、未知类别、重复分配(同一容器→同一库位出现多次)、超容量,或任何字段非法,均**整批返回 422** | `backend/app/main.py` + `validate_batch()` |

422 响应体 `detail` 为行级错误明细数组,每项含 `index`(从 0 开始的行号)、
`code`、`field`;前端收到后**清除旧结论并标出对应行**(行标红 + 字段红框 + 错误文案)。

错误码:`bad_slot`、`bad_container_id`、`unknown_category`、
`duplicate_id`、`duplicate_assignment`、`slot_over_capacity`、`row_format`。

### API

- `GET /api/health` → `{"status":"ok"}`
- `POST /api/verify`
  - 请求:`{"rows":[{"slot":3,"container_id":"A1","category":"A"}, ...]}`
  - 200:`{"results":[{"slot":1,"ok":true,"container_ids":["N1"],"conflicts":[]}, ...]}`
  - 422:`{"detail":[{"index":0,"code":"duplicate_id","field":"container_id"}, ...]}`

---

## 二、启动方式(Docker Compose,推荐)

需要 Docker 与 Compose v2。

```bash
# 默认:前端 http://localhost:8080 ,后端 http://localhost:8000
docker compose up --build

# 用环境变量覆盖宿主端口
WEB_PORT=9090 API_PORT=9000 docker compose up --build
# 或复制 .env.example 为 .env 后按需修改
```

打开 `http://localhost:${WEB_PORT:-8080}` 即可录入核验;
浏览器经 nginx 反代 `/api` 到 FastAPI(开发模式下由 Vite 代理)。

### 一次性验收服务 `verify`

```bash
docker compose --profile verify run --rm verify
```

该服务在同一容器内**真实构建前端、真实启动 FastAPI 与 nginx**,
然后依次执行:

1. **pytest** —— 规则矩阵、边界(库位 1/99、容量 4/5、编号长度与字符集)、
   排序规范化、API 200/422;
2. **Vitest** —— 前端 API 封装(真实请求体、422 抛错)与整页交互
   (逐库位通过/失败展示、422 清旧结论并标行、清空);
3. **Playwright(Chromium)** —— 针对运行中的真实前后端做端到端联调:
   合法批次逐库位结论与冲突对排序、重复编号 422、超容量 422、
   「先通过后 422 旧结论被清除」、边界值。

全部通过退出码为 0,任一失败非 0。

---

## 三、本地开发(不用 Docker)

后端(需 Python 3.12):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
pytest -q
```

前端(需 Node.js 20+):

```bash
cd frontend
npm ci            # 或 npm install
npm run dev       # http://localhost:5173 ,/api 代理到 :8000
npm test          # Vitest
npx playwright test   # 需要先起前后端;PLAYWRIGHT_BASE_URL 可覆盖目标地址
```

---

## 四、目录结构

```
backend/
  app/
    rules.py          # 唯一规则实现:校验 + 逐库位核验 + 排序规范化
    main.py           # FastAPI:/api/verify、/api/health、422
  tests/              # pytest(规则边界 + API)
  Dockerfile
frontend/
  src/
    api.ts            # /api/verify 调用与 422 异常
    types.ts          # 契约类型与错误码文案
    App.tsx           # 状态:提交、清旧结论、按行标错
    components/
      RowForm.tsx     # 录入表格(错误行/字段标红)
      ResultPanel.tsx # 逐库位通过/失败 + 实际冲突对
    *.test.ts(x)      # Vitest
  e2e/verify.e2e.ts   # Playwright 端到端
  Dockerfile  nginx.conf
docker-compose.yml    # web / api / verify(profile)
verify/               # 一次性验收镜像与入口脚本
```
