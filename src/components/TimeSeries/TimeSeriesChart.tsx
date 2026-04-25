import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TimeSeriesRecord } from "../../types/timeseries";

interface TimeSeriesChartProps {
  records: TimeSeriesRecord[];
}

export function TimeSeriesChart({ records }: TimeSeriesChartProps) {
  const data = records.map((record) => ({
    date: record.date,
    value: record.value,
    metric: record.metric,
    unit: record.unit
  }));

  return (
    <div className="h-[380px] rounded-xl border border-neutral-200 bg-white p-4">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 12, right: 18, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="#e5e5e5" vertical={false} />
          <XAxis dataKey="date" tick={{ fill: "#525252", fontSize: 12 }} minTickGap={28} stroke="#d4d4d4" />
          <YAxis tick={{ fill: "#525252", fontSize: 12 }} stroke="#d4d4d4" />
          <Tooltip
            contentStyle={{ background: "#ffffff", border: "1px solid #d4d4d4", borderRadius: 8, color: "#111111" }}
            formatter={(value) => [Number(value).toLocaleString(), "Value"]}
          />
          <Line type="monotone" dataKey="value" stroke="#b91c1c" strokeWidth={2.6} dot={false} activeDot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
