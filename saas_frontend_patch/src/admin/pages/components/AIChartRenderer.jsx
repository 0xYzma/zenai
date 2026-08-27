import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
  Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import DOMPurify from "dompurify";

export const InsightChart = ({ rows, chartType, isDark }) => {
  if (!Array.isArray(rows) || rows.length < 2 || chartType === "none" || chartType === "stat") return null;
  const keys = [...new Set(rows.flatMap((row) => Object.keys(row || {})))];
  const preferredX = ["date", "day", "hour", "status", "metric", "product_name", "category_name", "name"];
  const xKey = preferredX.find((key) => keys.includes(key))
    || keys.find((key) => rows.some((row) => typeof row?.[key] === "string"));
  const numericKeys = keys.filter((key) => key !== xKey && rows.some((row) => (
    typeof row?.[key] === "number" && Number.isFinite(row[key])
  ))).slice(0, 2);
  if (!xKey || numericKeys.length === 0) return null;
  const data = rows.slice(0, 30);
  const axisColor = isDark ? "#94a3b8" : "#64748b";
  const gridColor = isDark ? "#334155" : "#e2e8f0";
  const tooltipStyle = {
    background: isDark ? "#0f172a" : "#ffffff",
    border: `1px solid ${gridColor}`,
    borderRadius: 12,
    color: isDark ? "#f8fafc" : "#0f172a",
  };

  if (chartType === "pie") {
    return (
      <div className="mt-4 h-64" aria-label="AI insight pie chart" role="img" tabIndex={0}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey={numericKeys[0]} nameKey={xKey} outerRadius={82} label>
              {data.map((_, index) => <Cell key={index} fill={["#6366f1", "#14b8a6", "#f59e0b", "#f43f5e"][index % 4]} />)}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} /><Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  const Chart = chartType === "line" ? LineChart : BarChart;
  return (
    <div className="mt-4 h-64" aria-label={`AI insight ${chartType || "bar"} chart`} role="img" tabIndex={0}>
      <ResponsiveContainer width="100%" height="100%">
        <Chart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
          <CartesianGrid stroke={gridColor} strokeDasharray="3 3" />
          <XAxis dataKey={xKey} stroke={axisColor} tick={{ fontSize: 11 }} />
          <YAxis stroke={axisColor} tick={{ fontSize: 11 }} width={54} />
          <Tooltip contentStyle={tooltipStyle} /><Legend />
          {numericKeys.map((key, index) => chartType === "line"
            ? <Line key={key} type="monotone" dataKey={key} stroke={["#6366f1", "#14b8a6", "#f59e0b", "#f43f5e"][index]} strokeWidth={2} dot={false} />
            : <Bar key={key} dataKey={key} fill={["#6366f1", "#14b8a6", "#f59e0b", "#f43f5e"][index]} radius={[5, 5, 0, 0]} />)}
        </Chart>
      </ResponsiveContainer>
    </div>
  );
};

export const DataTable = ({ rows, isDark }) => {
  if (!Array.isArray(rows) || rows.length === 0) return null;
  const scalarKeys = [...new Set(
    rows.flatMap((row) => Object.keys(row || {})),
  )].filter((key) => rows.some((row) => (
    row?.[key] === null || ["string", "number", "boolean"].includes(typeof row?.[key])
  ))).filter((key) => !key.endsWith("_id")).slice(0, 6);
  if (scalarKeys.length === 0) return null;
  const label = (key) => key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  const value = (item) => {
    if (item === null || item === undefined) return "—";
    if (typeof item === "number") return new Intl.NumberFormat("en-BD", { maximumFractionDigits: 2 }).format(item);
    return String(item);
  };

  return (
    <div className="mt-4 max-w-full overflow-x-auto rounded-xl border border-slate-500/20" tabIndex={0} aria-label="Data table result">
      <table className="min-w-full text-left text-xs">
        <thead className={isDark ? "bg-slate-900/70" : "bg-slate-100"}>
          <tr>{scalarKeys.map((key) => <th key={key} className="whitespace-nowrap px-3 py-2 font-bold" scope="col">{DOMPurify.sanitize(label(key))}</th>)}</tr>
        </thead>
        <tbody>
          {rows.slice(0, 20).map((row, rowIndex) => (
            <tr key={rowIndex} className="border-t border-slate-500/15">
              {scalarKeys.map((key) => <td key={key} className="max-w-64 px-3 py-2">{DOMPurify.sanitize(value(row?.[key]))}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 20 && <div className="border-t border-slate-500/15 px-3 py-2 text-xs opacity-70">Showing 20 of {rows.length} rows</div>}
    </div>
  );
};
