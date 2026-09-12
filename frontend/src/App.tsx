import { useMemo, useState } from "react";
import { verifyBatch, VerifyRejectedError } from "./api";
import { RowForm } from "./components/RowForm";
import { ResultPanel } from "./components/ResultPanel";
import type { RowError, RowInput, SlotResult } from "./types";

const EMPTY_ROW: RowInput = { slot: "", containerId: "", category: "" };

function initialRows(): RowInput[] {
  return [{ ...EMPTY_ROW }, { ...EMPTY_ROW }];
}

export default function App() {
  const [rows, setRows] = useState<RowInput[]>(initialRows);
  const [results, setResults] = useState<SlotResult[] | null>(null);
  const [errorsByRow, setErrorsByRow] = useState<Map<number, RowError[]>>(
    new Map(),
  );
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const updateRow = (index: number, next: RowInput) => {
    setRows((prev) => prev.map((row, i) => (i === index ? next : row)));
  };

  const addRow = () => setRows((prev) => [...prev, { ...EMPTY_ROW }]);

  const removeRow = (index: number) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
    setErrorsByRow(new Map());
  };

  const clearAll = () => {
    setRows(initialRows());
    // 清除旧结论与错误标记
    setResults(null);
    setErrorsByRow(new Map());
    setSubmitError(null);
  };

  const submit = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const data = await verifyBatch(rows);
      setResults(data.results);
      setErrorsByRow(new Map());
    } catch (err) {
      if (err instanceof VerifyRejectedError) {
        // 422:整批拒绝 —— 清除旧结论,按行标出问题
        setResults(null);
        const grouped = new Map<number, RowError[]>();
        for (const e of err.errors) {
          const list = grouped.get(e.index) ?? [];
          list.push(e);
          grouped.set(e.index, list);
        }
        setErrorsByRow(grouped);
      } else {
        setResults(null);
        setSubmitError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setSubmitting(false);
    }
  };

  const shownResults = useMemo(() => results ?? [], [results]);

  return (
    <main className="page">
      <header>
        <h1>危险品同位禁配核验台</h1>
        <p className="subtitle">
          类别:A 酸类 / B 碱类 / O 氧化剂 / F 易燃品 / N 中性;
          无向禁配对 A-B、A-O、O-F,其余兼容。库位 1–99,每库位最多 4 个容器。
        </p>
      </header>

      <RowForm
        rows={rows}
        errorsByRow={errorsByRow}
        onChange={updateRow}
        onAdd={addRow}
        onRemove={removeRow}
        onSubmit={submit}
        onClear={clearAll}
        submitting={submitting}
      />

      {submitError && (
        <p className="batch-banner" role="alert" data-testid="submit-error">
          {submitError}
        </p>
      )}

      <ResultPanel results={shownResults} />
    </main>
  );
}
