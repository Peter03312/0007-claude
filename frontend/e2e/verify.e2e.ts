import { expect, test } from "@playwright/test";

/**
 * 真实前后端联调 E2E:页面 → FastAPI → 规则引擎 → 页面呈现。
 * 不打桩、不使用固定响应。
 */

async function fillRow(
  page: import("@playwright/test").Page,
  index: number,
  row: { slot: string; container: string; category: string },
) {
  await page.getByTestId(`slot-${index}`).fill(row.slot);
  await page.getByTestId(`container-${index}`).fill(row.container);
  await page.getByTestId(`category-${index}`).selectOption(row.category);
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
});

test("合法批次:逐库位显示通过/失败,且只呈现规范化冲突对", async ({
  page,
}) => {
  // 库位 1:O + F 冲突(冲突对 ASCII:BOX1 < FLAM2)
  await fillRow(page, 0, { slot: "1", container: "BOX1", category: "O" });
  await fillRow(page, 1, { slot: "1", container: "FLAM2", category: "F" });
  // 库位 2:A + N 兼容
  await page.getByTestId("add-row").click();
  await fillRow(page, 2, { slot: "2", container: "NEUT3", category: "A" });
  await page.getByTestId("add-row").click();
  await fillRow(page, 3, { slot: "2", container: "NEUT4", category: "N" });
  // 库位 3:三个容器两对冲突(A-B、A-O),验证排序
  await page.getByTestId("add-row").click();
  await fillRow(page, 4, { slot: "3", container: "C3", category: "B" });
  await page.getByTestId("add-row").click();
  await fillRow(page, 5, { slot: "3", container: "C1", category: "A" });
  await page.getByTestId("add-row").click();
  await fillRow(page, 6, { slot: "3", container: "C2", category: "O" });

  await page.getByTestId("submit").click();

  await expect(page.getByTestId("results-summary")).toContainText(
    "共 3 个库位,1 个通过,2 个失败",
  );

  // 库位按数值升序出现在 DOM 中
  const slots = await page
    .locator('[data-testid^="slot-result-"]')
    .evaluateAll((nodes) => nodes.map((n) => Number((n as HTMLElement).dataset.slot)));
  expect(slots).toEqual([1, 2, 3]);

  // 库位 1 失败,只有一对冲突
  const card1 = page.getByTestId("slot-result-1");
  await expect(card1).toHaveAttribute("data-ok", "false");
  await expect(card1.getByText("✕ 失败")).toBeVisible();
  const pairs1 = await card1
    .locator('[data-testid^="conflict-1-"]')
    .allInnerTexts();
  expect(pairs1).toEqual(["BOX1 ⚠ FLAM2"]);

  // 库位 2 通过,无冲突区
  const card2 = page.getByTestId("slot-result-2");
  await expect(card2).toHaveAttribute("data-ok", "true");
  await expect(card2.getByText("✓ 通过")).toBeVisible();
  await expect(page.getByTestId("conflicts-2")).toHaveCount(0);

  // 库位 3:冲突对按首项再按次项 ASCII 排序:C1-C2 < C1-C3
  const card3 = page.getByTestId("slot-result-3");
  const pairs3 = await card3
    .locator('[data-testid^="conflict-3-"]')
    .allInnerTexts();
  expect(pairs3).toEqual(["C1 ⚠ C2", "C1 ⚠ C3"]);
});

test("重复编号触发 422:清除旧结论并标出对应行", async ({ page }) => {
  await fillRow(page, 0, { slot: "1", container: "DUP1", category: "N" });
  await fillRow(page, 1, { slot: "2", container: "DUP1", category: "A" });

  await page.getByTestId("submit").click();

  await expect(page.getByTestId("batch-banner")).toContainText(
    "整批被拒绝(422)",
  );
  await expect(page.getByTestId("row-0")).toHaveClass(/row-error/);
  await expect(page.getByTestId("row-1")).toHaveClass(/row-error/);
  await expect(page.getByTestId("container-0")).toHaveClass(/invalid/);
  await expect(page.getByTestId("container-1")).toHaveClass(/invalid/);
  // 没有任何库位结论
  await expect(page.locator('[data-testid^="slot-result-"]')).toHaveCount(0);
});

test("超容量(每库位 5 个)触发 422 并标出该库位所有行", async ({
  page,
}) => {
  await fillRow(page, 0, { slot: "9", container: "C01", category: "N" });
  await fillRow(page, 1, { slot: "9", container: "C02", category: "N" });
  for (let i = 2; i <= 4; i++) {
    await page.getByTestId("add-row").click();
    await fillRow(page, i, {
      slot: "9",
      container: `C0${i + 1}`,
      category: "N",
    });
  }

  await page.getByTestId("submit").click();

  await expect(page.getByTestId("batch-banner")).toBeVisible();
  for (let i = 0; i <= 4; i++) {
    await expect(page.getByTestId(`row-${i}`)).toHaveClass(/row-error/);
  }
  await expect(page.locator('[data-testid^="slot-result-"]')).toHaveCount(0);
});

test("先通过后 422:旧结论被清除", async ({ page }) => {
  await fillRow(page, 0, { slot: "1", container: "OK1", category: "N" });
  await fillRow(page, 1, { slot: "1", container: "OK2", category: "N" });
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("slot-result-1")).toBeVisible();

  // 改成未知类别(select 无法选择非法值,直接用接口视角:用非法库位号制造 422)
  await page.getByTestId("slot-0").fill("100");
  await page.getByTestId("submit").click();

  await expect(page.getByTestId("batch-banner")).toBeVisible();
  await expect(page.getByTestId("slot-result-1")).toHaveCount(0);
  await expect(page.getByTestId("slot-0")).toHaveClass(/invalid/);
});

test("边界:库位 99 与 12 位编号合法;库位 0 与小写编号 422", async ({
  page,
}) => {
  // 合法边界
  await fillRow(page, 0, { slot: "99", container: "ABCDEFGHIJKL", category: "A" });
  await fillRow(page, 1, { slot: "1", container: "Z", category: "B" });
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("results-summary")).toContainText("共 2 个库位");

  // 清空重来:非法边界
  await page.getByTestId("clear-rows").click();
  await fillRow(page, 0, { slot: "0", container: "lowercase", category: "A" });
  await fillRow(page, 1, { slot: "5", container: "GOOD5", category: "N" });
  await page.getByTestId("submit").click();

  await expect(page.getByTestId("row-0")).toHaveClass(/row-error/);
  await expect(page.getByTestId("slot-0")).toHaveClass(/invalid/);
  await expect(page.getByTestId("container-0")).toHaveClass(/invalid/);
  // 第 1 行本身字段合法,但整批拒绝,同样无结论
  await expect(page.locator('[data-testid^="slot-result-"]')).toHaveCount(0);
});
