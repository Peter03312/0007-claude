"""FastAPI 应用:危险品同位禁配核验 API。"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from .rules import validate_batch, verify

app = FastAPI(
    title="危险品同位禁配核验台",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class BatchRequest(BaseModel):
    # 行内字段与非对象行均由规则引擎做精确校验并回传行号,
    # 这里保留最宽类型,避免 Pydantic 提前拦截导致无法标行
    rows: list[Any] = Field(default_factory=list)


class SlotResult(BaseModel):
    slot: int
    ok: bool
    container_ids: list[str]
    conflicts: list[list[str]]


class BatchResponse(BaseModel):
    results: list[SlotResult]


class RowError(BaseModel):
    # 允许携带 slot/count/container_id 等上下文字段
    model_config = ConfigDict(extra="allow")

    index: int
    code: str
    field: str | None


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/verify", response_model=BatchResponse)
def verify_batch(request: BatchRequest) -> BatchResponse:
    assignments, errors = validate_batch(request.rows)
    if errors:
        # 整批拒绝:任何行级/跨行错误都返回 422,前端清旧结论并标行
        raise HTTPException(status_code=422, detail=errors)
    return BatchResponse(results=verify(assignments))
