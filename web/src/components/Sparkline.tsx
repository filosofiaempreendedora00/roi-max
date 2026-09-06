/** Curva de capital do backtest. SVG puro: sem biblioteca, sem peso. */
export function Sparkline({ data, height = 90 }: { data: number[]; height?: number }) {
  if (data.length < 2) return <p className="muted">Sem dados suficientes para a curva.</p>;

  const w = 600;
  const min = Math.min(0, ...data);
  const max = Math.max(0, ...data);
  const span = max - min || 1;
  const x = (i: number) => (i / (data.length - 1)) * w;
  const y = (v: number) => height - ((v - min) / span) * height;

  const path = data.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const last = data[data.length - 1];
  const stroke = last >= 0 ? "var(--pos)" : "var(--neg)";

  return (
    <svg className="spark" viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" role="img"
         aria-label={`Curva de capital terminando em ${last.toFixed(2)} unidades`}>
      <line x1="0" x2={w} y1={y(0)} y2={y(0)} stroke="var(--line)" strokeDasharray="4 4" />
      <path d={path} fill="none" stroke={stroke} strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
