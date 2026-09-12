import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import App from "./App";

function mockFetchOnce(response: Response) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(() => Promise.resolve(response)),
  );
}

function okResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function unprocessable(detail: unknown) {
  return new Response(JSON.stringify({ detail }), {
    status: 422,
    headers: { "Content-Type": "application/json" },
  });
}

async function fillRow(
  user: ReturnType<typeof userEvent.setup>,
  index: number,
  values: { slot?: string; container?: string; category?: string },
) {
  if (values.slot !== undefined) {
    await user.clear(screen.getByTestId(`slot-${index}`));
    await user.type(screen.getByTestId(`slot-${index}`), values.slot);
  }
  if (values.container !== undefined) {
    await user.clear(screen.getByTestId(`container-${index}`));
    await user.type(
      screen.getByTestId(`container-${index}`),
      values.container,
    );
  }
  if (values.category !== undefined) {
    await user.selectOptions(
      screen.getByTestId(`category-${index}`),
      values.category,
    );
  }
}

describe("App 核验台交互", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("合法提交后逐库位显示通过/失败与规范化冲突对", async () => {
    mockFetchOnce(
      okResponse({
        results: [
          {
            slot: 1,
            ok: true,
            container_ids: ["N1"],
            conflicts: [],
          },
          {
            slot: 3,
            ok: false,
            container_ids: ["A1", "B1"],
            conflicts: [["A1", "B1"]],
          },
        ],
      }),
    );
    const user = userEvent.setup();
    render(<App />);

    await fillRow(user, 0, {
      slot: "1",
      container: "N1",
      category: "N",
    });
    await fillRow(user, 1, {
      slot: "3",
      container: "A1",
      category: "A",
    });
    await user.click(screen.getByTestId("add-row"));
    await fillRow(user, 2, {
      slot: "3",
      container: "B1",
      category: "B",
    });

    await user.click(screen.getByTestId("submit"));

    const summary = await screen.findByTestId("results-summary");
    expect(summary).toHaveTextContent("共 2 个库位,1 个通过,1 个失败");

    const passCard = screen.getByTestId("slot-result-1");
    expect(passCard).toHaveAttribute("data-ok", "true");
    expect(
      within(passCard).getByText("✓ 通过"),
    ).toBeInTheDocument();

    const failCard = screen.getByTestId("slot-result-3");
    expect(failCard).toHaveAttribute("data-ok", "false");
    expect(
      within(failCard).getByText("✕ 失败"),
    ).toBeInTheDocument();
    expect(
      within(failCard).getByText("A1"),
    ).toBeInTheDocument();
    expect(within(failCard).getByText("B1")).toBeInTheDocument();
  });

  it("422 时清除旧结论并标出对应行", async () => {
    // 第一次:合法,产生旧结论
    mockFetchOnce(
      okResponse({
        results: [
          { slot: 1, ok: true, container_ids: ["N1"], conflicts: [] },
        ],
      }),
    );
    const user = userEvent.setup();
    render(<App />);
    await fillRow(user, 0, { slot: "1", container: "N1", category: "N" });
    await user.click(screen.getByTestId("submit"));
    expect(await screen.findByTestId("slot-result-1")).toBeInTheDocument();

    // 第二次:422(重复编号:第 0、1 行;第 2 行库位越界)
    mockFetchOnce(
      unprocessable([
        { index: 0, code: "duplicate_id", field: "container_id" },
        { index: 1, code: "duplicate_id", field: "container_id" },
        { index: 2, code: "bad_slot", field: "slot" },
      ]),
    );
    await user.click(screen.getByTestId("add-row"));
    await user.click(screen.getByTestId("submit"));

    // 旧结论被清除
    expect(screen.queryByTestId("slot-result-1")).not.toBeInTheDocument();
    expect(screen.getByTestId("results-empty")).toBeInTheDocument();
    // 整批拒绝横幅
    expect(screen.getByTestId("batch-banner")).toHaveTextContent(
      "整批被拒绝(422)",
    );
    // 对应行被标红
    expect(screen.getByTestId("row-0")).toHaveClass("row-error");
    expect(screen.getByTestId("row-1")).toHaveClass("row-error");
    expect(screen.getByTestId("row-2")).toHaveClass("row-error");
    expect(
      within(screen.getByTestId("row-2")).getByText(
        /库位号必须是 1 至 99 的整数/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByTestId("slot-2")).toHaveClass("invalid");
  });

  it("未知类别行由后端 422 标出类别字段", async () => {
    mockFetchOnce(
      unprocessable([
        { index: 0, code: "unknown_category", field: "category" },
      ]),
    );
    const user = userEvent.setup();
    render(<App />);
    await fillRow(user, 0, { slot: "1", container: "C1" });
    await user.click(screen.getByTestId("submit"));

    expect(screen.getByTestId("category-0")).toHaveClass("invalid");
    expect(screen.getByTestId("row-0")).toHaveClass("row-error");
  });

  it("清空按钮清除录入、旧结论与错误标记", async () => {
    mockFetchOnce(
      unprocessable([
        { index: 0, code: "bad_container_id", field: "container_id" },
      ]),
    );
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByTestId("submit"));
    expect(await screen.findByTestId("batch-banner")).toBeInTheDocument();

    await user.click(screen.getByTestId("clear-rows"));
    expect(screen.queryByTestId("batch-banner")).not.toBeInTheDocument();
    expect(screen.queryAllByTestId(/^row-/)).toHaveLength(2);
    expect(screen.getByTestId("slot-0")).toHaveValue("");
    expect(screen.getByTestId("results-empty")).toBeInTheDocument();
  });
});
