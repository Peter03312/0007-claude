import type {
  RowError,
  RowInput,
  VerifyResponse,
  VerifyRowPayload,
} from "./types";

/**
 * 提交整批录入到 FastAPI /api/verify。
 *
 * 成功(200):返回逐库位结论。
 * 整批非法(422):抛出携带后端行级错误明细的 VerifyRejectedError,
 *   调用方负责清除旧结论并按行号标出错误。
 */
export class VerifyRejectedError extends Error {
  readonly errors: RowError[];

  constructor(errors: RowError[]) {
    super("整批核验被拒绝(422)");
    this.name = "VerifyRejectedError";
    this.errors = errors;
  }
}

/**
 * 把表单行转成后端载荷。
 *
 * 格式性预检(slot 是否整数、编号是否非空)不在前端做拒绝:
 * 全部原样提交给后端,由唯一的规则实现返回权威 422 明细,
 * 前端只负责按错误码标行,避免出现与后端不一致的"假校验"。
 */
export function toPayload(rows: RowInput[]): VerifyRowPayload[] {
  return rows.map((row) => ({
    slot: Number(row.slot),
    container_id: row.containerId,
    category: row.category,
  }));
}

export async function verifyBatch(
  rows: RowInput[],
  fetchImpl: typeof fetch = fetch,
): Promise<VerifyResponse> {
  const response = await fetchImpl("/api/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rows: toPayload(rows) }),
  });

  if (response.status === 422) {
    const body = (await response.json()) as { detail?: RowError[] };
    throw new VerifyRejectedError(
      Array.isArray(body.detail) ? body.detail : [],
    );
  }

  if (!response.ok) {
    throw new Error(`核验服务异常:HTTP ${response.status}`);
  }

  return (await response.json()) as VerifyResponse;
}
