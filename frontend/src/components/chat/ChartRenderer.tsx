"use client";

import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from "recharts";
import type { PieLabelRenderProps } from "recharts";

interface ChartRendererProps {
  chartType: string;
  chartData: Record<string, unknown>[];
}

const COLORS = ["#4F46E5", "#14B8A6", "#F59E0B", "#EF4444", "#22C55E", "#8B5CF6", "#EC4899"];

export function ChartRenderer({ chartType, chartData }: ChartRendererProps) {
  if (!chartData || chartData.length === 0) return null;

  if (chartType === "stat") {
    const value = chartData[0]?.value;
    return (
      <div className="flex items-center justify-center p-6">
        <div className="text-4xl font-bold text-primary">
          {typeof value === "number" ? value.toLocaleString() : String(value)}
        </div>
      </div>
    );
  }

  const keys = Object.keys(chartData[0]).filter((k) => k !== "name" && k !== "date" && k !== "label");
  const xKey = chartData[0].date ? "date" : chartData[0].name ? "name" : Object.keys(chartData[0])[0];
  const yKey = keys[0] || "value";

  return (
    <div className="w-full h-64 mt-3">
      <ResponsiveContainer width="100%" height="100%">
        {chartType === "line" ? (
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
            <XAxis dataKey={String(xKey)} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Line type="monotone" dataKey={String(yKey)} stroke="#4F46E5" strokeWidth={2} dot={{ fill: "#4F46E5" }} />
          </LineChart>
        ) : chartType === "bar" ? (
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
            <XAxis dataKey={String(xKey)} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Bar dataKey={String(yKey)} fill="#4F46E5" radius={[4, 4, 0, 0]} />
          </BarChart>
        ) : chartType === "pie" ? (
          <PieChart>
            <Pie
              data={chartData}
              dataKey={String(yKey)}
              nameKey={String(xKey)}
              cx="50%"
              cy="50%"
              outerRadius={80}
              label={({ name, percent }: PieLabelRenderProps) => `${name ?? ""} ${(((percent as number) ?? 0) * 100).toFixed(0)}%`}
            >
              {chartData.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        ) : chartType === "scatter" ? (
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
            <XAxis dataKey="x" type="number" tick={{ fontSize: 12 }} />
            <YAxis dataKey="y" type="number" tick={{ fontSize: 12 }} />
            <Tooltip />
            <Scatter data={chartData} fill="#4F46E5" />
          </ScatterChart>
        ) : (
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
            <XAxis dataKey={String(xKey)} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Bar dataKey={String(yKey)} fill="#4F46E5" radius={[4, 4, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
