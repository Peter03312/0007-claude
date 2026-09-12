/** 与后端 /api/verify 契约一致的类型定义。 */

export type Category = "A" | "B" | "O" | "F" | "N";

export const CATEGORY_LABELS: Record<Category, string> = {
  A: "A 酸类",
  B: "B 碱类",
  O: "O 氧化剂",
  F: "F 易燃品",
  N: "N 中性",
};

export const CATEGORIES: Category[] = ["A", "B", "O", "F", "N"];

export interface RowInput {
  slot: string;
  containerId: string;
  category: "" | Category;
}

export interface VerifyRowPayload {
  slot: number;
  container_id: string;
  category: string;
}

export interface SlotResult {
  slot: number;
  ok: boolean;
  container_ids: string[];
  conflicts: [string, string][];
}

export interface VerifyResponse {
  results: SlotResult[];
}

/** 后端 422 错误码,与 backend/app/rules.py 保持一致。 */
export type RowErrorCode =
  | "row_format"
  | "bad_slot"
  | "bad_container_id"
  | "unknown_category"
  | "duplicate_id"
  | "duplicate_assignment"
  | "slot_over_capacity";

export interface RowError {
  index: number;
  code: RowErrorCode | string;
  field: "slot" | "container_id" | "category" | null;
  container_id?: string;
  slot?: number;
  count?: number;
  limit?: number;
}

export const ERROR_MESSAGES: Record<string, string> = {
  row_format: "该行格式无法识别",
  bad_slot: "库位号必须是 1 至 99 的整数",
  bad_container_id: "容器编号须为 1 至 12 位大写字母或数字",
  unknown_category: "类别仅允许 A / B / O / F / N",
  duplicate_id: "容器编号在本批中重复",
  duplicate_assignment: "同一容器重复分配到该库位",
  slot_over_capacity: "该库位超过 4 个容器的容量上限",
};
