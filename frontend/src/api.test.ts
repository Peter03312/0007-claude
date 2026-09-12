import { describe, expect, it, vi } from "vitest";
import { toPayload, verifyBatch, VerifyRejectedError } from "./api";
import type { RowInput } from "./types";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("toPayload", () => {
  it("原样把字符串字段映射成后端 snake_case 载荷,不做本地放行", () => {
    const rows: RowInput[] = [
      { slot: "12", containerId: "AB1", category: "A" },
      { slot: "", containerId: "x", category: "" },
    ];
    expect(toPayload(rows)).toEqual([
      { slot: 12, container_id: "AB1", category: "A" },
      { slot: 0, container_id: "x", category: "" },
    ]);
  });
});

describe("verifyBatch", () => {
  it("200 时返回逐库位结论", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, {
        results: [
          {
            slot: 3,
            ok: false,
            container_ids: ["A1", "B1"],
            conflicts: [["A1", "B1"]],
          },
        ],
      }),
    );

    const data = await verifyBatch([], fetchMock);
    expect(data.results[0].slot).toBe(3);
    expect(data.results[0].conflicts).toEqual([["A1", "B1"]]);
    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
  });

  it("422 时抛出携带行级明细的 VerifyRejectedError", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(422, {
        detail: [
          { index: 0, code: "bad_slot", field: "slot" },
          { index: 2, code: "duplicate_id", field: "container_id" },
        ],
      }),
    );

    const error = await verifyBatch([], fetchMock).catch((e) => e);
    expect(error).toBeInstanceOf(VerifyRejectedError);
    expect((error as VerifyRejectedError).errors).toEqual([
      { index: 0, code: "bad_slot", field: "slot" },
      { index: 2, code: "duplicate_id", field: "container_id" },
    ]);
  });

  it("其他非 2xx 状态抛出通用错误", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(500, { detail: "boom" }));
    await expect(verifyBatch([], fetchMock)).rejects.toThrow(/HTTP 500/);
  });

  it("真实地把行内容写入请求体(非固定响应)", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(200, { results: [] }));
    const rows: RowInput[] = [
      { slot: "7", containerId: "Z9", category: "O" },
    ];
    await verifyBatch(rows, fetchMock);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      rows: [{ slot: 7, container_id: "Z9", category: "O" }],
    });
  });
});
