import { useEffect, useRef, useState, type ReactNode } from "react";
import type { Contribution, EventRow, HistogramBin } from "../api";
import { pct } from "../format";

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(600);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    setWidth(element.clientWidth || 600);
    const observer = new ResizeObserver((entries) => {
      const next = Math.round(entries[0].contentRect.width);
      if (next > 0) setWidth(next);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

interface TooltipState {
  x: number;
  y: number;
  content: ReactNode;
}

function Tooltip({ state, width }: { state: TooltipState | null; width: number }) {
  if (!state) return null;
  const left = Math.max(0, Math.min(state.x + 12, width - 200));
  return (
    <div className="tooltip" style={{ left, top: Math.max(0, state.y - 10) }}>
      {state.content}
    </div>
  );
}

function niceMax(value: number): number {
  if (value <= 0) return 1;
  const exponent = Math.pow(10, Math.floor(Math.log10(value)));
  const fraction = value / exponent;
  const nice = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
  return nice * exponent;
}

function ticks(max: number, count = 4): number[] {
  const step = max / count;
  return Array.from({ length: count + 1 }, (_, index) => index * step);
}

/** Bar path with a 4px rounded data-end and a square baseline end. */
function columnPath(x: number, y: number, width: number, height: number, radius = 4): string {
  if (height <= 0) return "";
  const r = Math.min(radius, width / 2, height);
  return `M${x},${y + height} L${x},${y + r} Q${x},${y} ${x + r},${y} L${x + width - r},${y} Q${x + width},${y} ${x + width},${y + r} L${x + width},${y + height} Z`;
}

function barPathRight(x: number, y: number, width: number, height: number, radius = 4): string {
  if (width <= 0) return "";
  const r = Math.min(radius, height / 2, width);
  return `M${x},${y} L${x + width - r},${y} Q${x + width},${y} ${x + width},${y + r} L${x + width},${y + height - r} Q${x + width},${y + height} ${x + width - r},${y + height} L${x},${y + height} Z`;
}

function barPathLeft(x: number, y: number, width: number, height: number, radius = 4): string {
  if (width <= 0) return "";
  const r = Math.min(radius, height / 2, width);
  const left = x - width;
  return `M${x},${y} L${left + r},${y} Q${left},${y} ${left},${y + r} L${left},${y + height - r} Q${left},${y + height} ${left + r},${y + height} L${x},${y + height} Z`;
}

// ---------------------------------------------------------------------------
// Risk score histogram
// ---------------------------------------------------------------------------

export function RiskHistogram({ bins, threshold }: { bins: HistogramBin[]; threshold: number }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [tip, setTip] = useState<TooltipState | null>(null);
  const labeled = bins.some((bin) => bin.fraud !== undefined);
  const height = 220;
  const margin = { top: 12, right: 12, bottom: 28, left: 44 };
  const innerWidth = Math.max(100, width - margin.left - margin.right);
  const innerHeight = height - margin.top - margin.bottom;
  // Square-root scale keeps the small high-risk bins visible next to the large low-risk bin.
  // Labeled data shows known-legit and known-fraud side by side (not stacked:
  // stacking on a square-root axis would distort segment proportions).
  const maxCount = niceMax(
    Math.max(...bins.map((bin) => (labeled ? Math.max(bin.fraud ?? 0, bin.legit ?? 0) : bin.count)), 1),
  );
  const y = (value: number) => innerHeight - (Math.sqrt(value) / Math.sqrt(maxCount)) * innerHeight;
  const band = innerWidth / bins.length;
  const barWidth = labeled ? Math.min(12, (band - 4) / 2) : Math.min(24, band - 2);
  const tickValues = [0, maxCount / 16, maxCount / 4, maxCount].map((value) => Math.round(value));

  return (
    <div className="chart" ref={ref}>
      {labeled && (
        <div className="legend" style={{ marginBottom: 6 }}>
          <span>
            <span className="swatch" style={{ background: "var(--series-1)" }} /> Known legitimate
          </span>
          <span>
            <span className="swatch" style={{ background: "var(--series-2)" }} /> Known fraud
          </span>
          <span className="muted">Square-root scale</span>
        </div>
      )}
      <svg width={width} height={height} role="img" aria-label="Distribution of risk scores">
        <g transform={`translate(${margin.left},${margin.top})`}>
          {tickValues.map((value) => (
            <g key={value}>
              <line className="grid-line" x1={0} x2={innerWidth} y1={y(value)} y2={y(value)} />
              <text x={-8} y={y(value) + 4} textAnchor="end" className="num">
                {value.toLocaleString()}
              </text>
            </g>
          ))}
          {bins.map((bin, index) => {
            const x = labeled ? index * band + (band - (barWidth * 2 + 2)) / 2 : index * band + (band - barWidth) / 2;
            const hover = (event: React.PointerEvent | React.FocusEvent) => {
              const rect = (event.currentTarget as SVGElement).ownerSVGElement!.getBoundingClientRect();
              const clientX = "clientX" in event ? event.clientX : rect.left + margin.left + x;
              setTip({
                x: clientX - rect.left,
                y: margin.top + y(bin.count),
                content: (
                  <>
                    <div className="tt-value">{bin.count.toLocaleString()} customers</div>
                    <div className="tt-row">
                      Score {Math.round(bin.start * 100)}–{Math.round(bin.end * 100)}
                    </div>
                    {labeled && (
                      <>
                        <div className="tt-row">
                          <span className="tt-key" style={{ background: "var(--series-2)" }} /> {bin.fraud} known fraud
                        </div>
                        <div className="tt-row">
                          <span className="tt-key" style={{ background: "var(--series-1)" }} /> {bin.legit} known legitimate
                        </div>
                      </>
                    )}
                  </>
                ),
              });
            };
            const fraud = bin.fraud ?? 0;
            const legit = bin.legit ?? 0;
            return (
              <g
                key={index}
                tabIndex={0}
                onPointerMove={hover}
                onFocus={hover}
                onPointerLeave={() => setTip(null)}
                onBlur={() => setTip(null)}
              >
                <rect x={index * band} y={0} width={band} height={innerHeight} fill="transparent" />
                {labeled ? (
                  <>
                    <path d={columnPath(x, y(legit), barWidth, innerHeight - y(legit))} fill="var(--series-1)" />
                    <path
                      d={columnPath(x + barWidth + 2, y(fraud), barWidth, innerHeight - y(fraud))}
                      fill="var(--series-2)"
                    />
                  </>
                ) : (
                  <path d={columnPath(x, y(bin.count), barWidth, innerHeight - y(bin.count))} fill="var(--series-1)" />
                )}
              </g>
            );
          })}
          <line className="axis-line" x1={0} x2={innerWidth} y1={innerHeight} y2={innerHeight} />
          <line
            x1={threshold * innerWidth}
            x2={threshold * innerWidth}
            y1={-4}
            y2={innerHeight}
            stroke="var(--text)"
            strokeWidth={1.5}
          />
          <text
            x={threshold * innerWidth + (threshold > 0.8 ? -6 : 6)}
            y={8}
            textAnchor={threshold > 0.8 ? "end" : "start"}
            style={{ fill: "var(--text)" }}
          >
            Alert threshold {Math.round(threshold * 100)}
          </text>
          {[0, 25, 50, 75, 100].map((value) => (
            <text key={value} x={(value / 100) * innerWidth} y={innerHeight + 18} textAnchor="middle" className="num">
              {value}
            </text>
          ))}
        </g>
      </svg>
      <Tooltip state={tip} width={width} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// ROC / precision-recall curve
// ---------------------------------------------------------------------------

export function CurveChart({
  points,
  xLabel,
  yLabel,
  diagonal = false,
  baseline,
}: {
  points: [number, number][];
  xLabel: string;
  yLabel: string;
  diagonal?: boolean;
  baseline?: number;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [tip, setTip] = useState<TooltipState | null>(null);
  const [cross, setCross] = useState<number | null>(null);
  const height = 240;
  const margin = { top: 10, right: 14, bottom: 34, left: 42 };
  const innerWidth = Math.max(100, width - margin.left - margin.right);
  const innerHeight = height - margin.top - margin.bottom;
  const sx = (value: number) => value * innerWidth;
  const sy = (value: number) => innerHeight - value * innerHeight;
  const line = points.map(([a, b], index) => `${index ? "L" : "M"}${sx(a)},${sy(b)}`).join(" ");
  const area = points.length ? `${line} L${sx(points[points.length - 1][0])},${innerHeight} L${sx(points[0][0])},${innerHeight} Z` : "";

  const move = (event: React.PointerEvent<SVGRectElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const xValue = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    let best = 0;
    for (let index = 1; index < points.length; index += 1) {
      if (Math.abs(points[index][0] - xValue) < Math.abs(points[best][0] - xValue)) best = index;
    }
    const point = points[best];
    if (!point) return;
    setCross(best);
    setTip({
      x: margin.left + sx(point[0]),
      y: margin.top + sy(point[1]),
      content: (
        <>
          <div className="tt-value">
            {yLabel} {pct(point[1], 1)}
          </div>
          <div className="tt-row">
            {xLabel} {pct(point[0], 1)}
          </div>
        </>
      ),
    });
  };

  return (
    <div className="chart" ref={ref}>
      <svg width={width} height={height} role="img" aria-label={`${yLabel} against ${xLabel}`}>
        <g transform={`translate(${margin.left},${margin.top})`}>
          {[0, 0.25, 0.5, 0.75, 1].map((value) => (
            <g key={value}>
              <line className="grid-line" x1={0} x2={innerWidth} y1={sy(value)} y2={sy(value)} />
              <text x={-8} y={sy(value) + 4} textAnchor="end" className="num">
                {value}
              </text>
              <text x={sx(value)} y={innerHeight + 16} textAnchor="middle" className="num">
                {value}
              </text>
            </g>
          ))}
          {diagonal && <line x1={0} y1={innerHeight} x2={innerWidth} y2={0} stroke="var(--axis)" strokeWidth={1} />}
          {baseline !== undefined && (
            <line x1={0} x2={innerWidth} y1={sy(baseline)} y2={sy(baseline)} stroke="var(--axis)" strokeWidth={1} />
          )}
          <path d={area} fill="var(--series-1)" opacity={0.1} />
          <path d={line} fill="none" stroke="var(--series-1)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          <line className="axis-line" x1={0} x2={innerWidth} y1={innerHeight} y2={innerHeight} />
          {cross !== null && points[cross] && (
            <>
              <line x1={sx(points[cross][0])} x2={sx(points[cross][0])} y1={0} y2={innerHeight} stroke="var(--axis)" />
              <circle
                cx={sx(points[cross][0])}
                cy={sy(points[cross][1])}
                r={4.5}
                fill="var(--series-1)"
                stroke="var(--surface)"
                strokeWidth={2}
              />
            </>
          )}
          <text x={innerWidth / 2} y={innerHeight + 30} textAnchor="middle">
            {xLabel}
          </text>
          <text transform={`translate(${-32},${innerHeight / 2}) rotate(-90)`} textAnchor="middle">
            {yLabel}
          </text>
          <rect
            x={0}
            y={0}
            width={innerWidth}
            height={innerHeight}
            fill="transparent"
            onPointerMove={move}
            onPointerLeave={() => {
              setTip(null);
              setCross(null);
            }}
          />
        </g>
      </svg>
      <Tooltip state={tip} width={width} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Horizontal bar list (feature importance, attribute counts)
// ---------------------------------------------------------------------------

export interface BarRow {
  key: string;
  label: string;
  value: number;
  color?: string;
  detail?: string;
}

export function BarList({
  rows,
  format = (value) => value.toLocaleString(),
  legend,
}: {
  rows: BarRow[];
  format?: (value: number) => string;
  legend?: { label: string; color: string }[];
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [tip, setTip] = useState<TooltipState | null>(null);
  const labelWidth = Math.min(220, Math.max(120, width * 0.36));
  const valueWidth = 64;
  const rowHeight = 28;
  const barHeight = 16;
  const innerWidth = Math.max(40, width - labelWidth - valueWidth - 8);
  const max = Math.max(...rows.map((row) => row.value), 1e-9);
  const height = rows.length * rowHeight;
  return (
    <div className="chart" ref={ref}>
      {legend && legend.length > 1 && (
        <div className="legend" style={{ marginBottom: 8 }}>
          {legend.map((item) => (
            <span key={item.label}>
              <span className="swatch" style={{ background: item.color }} /> {item.label}
            </span>
          ))}
        </div>
      )}
      <svg width={width} height={height} role="img" aria-label="Bar chart">
        {rows.map((row, index) => {
          const y = index * rowHeight;
          const barWidth = (row.value / max) * innerWidth;
          const hover = (event: React.PointerEvent | React.FocusEvent) => {
            const rect = (event.currentTarget as SVGElement).ownerSVGElement!.getBoundingClientRect();
            const clientX = "clientX" in event ? event.clientX - rect.left : labelWidth + barWidth;
            setTip({
              x: clientX,
              y: y,
              content: (
                <>
                  <div className="tt-value">{format(row.value)}</div>
                  <div className="tt-row">{row.label}</div>
                  {row.detail && <div className="tt-row">{row.detail}</div>}
                </>
              ),
            });
          };
          return (
            <g
              key={row.key}
              tabIndex={0}
              onPointerMove={hover}
              onFocus={hover}
              onPointerLeave={() => setTip(null)}
              onBlur={() => setTip(null)}
            >
              <rect x={0} y={y} width={width} height={rowHeight} fill="transparent" />
              <text x={labelWidth - 10} y={y + rowHeight / 2 + 4} textAnchor="end" style={{ fill: "var(--text-2)", fontSize: 12 }}>
                {row.label.length > 34 ? `${row.label.slice(0, 33)}…` : row.label}
              </text>
              <path
                d={barPathRight(labelWidth, y + (rowHeight - barHeight) / 2, Math.max(barWidth, 1.5), barHeight)}
                fill={row.color ?? "var(--series-1)"}
              />
              <text x={labelWidth + barWidth + 6} y={y + rowHeight / 2 + 4} className="num" style={{ fill: "var(--text-2)" }}>
                {format(row.value)}
              </text>
            </g>
          );
        })}
      </svg>
      <Tooltip state={tip} width={width} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Grouped columns (model comparison)
// ---------------------------------------------------------------------------

export function GroupedColumns({
  categories,
  series,
  domainMax = 1,
  format = (value) => value.toFixed(3),
}: {
  categories: { key: string; label: string }[];
  series: { key: string; label: string; color: string; values: Record<string, number | null> }[];
  domainMax?: number;
  format?: (value: number) => string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [tip, setTip] = useState<TooltipState | null>(null);
  const height = 230;
  const margin = { top: 16, right: 8, bottom: 30, left: 38 };
  const innerWidth = Math.max(100, width - margin.left - margin.right);
  const innerHeight = height - margin.top - margin.bottom;
  const band = innerWidth / Math.max(categories.length, 1);
  const barWidth = Math.min(24, (band * 0.7) / series.length);
  const groupWidth = barWidth * series.length + 2 * (series.length - 1);
  const y = (value: number) => innerHeight - (value / domainMax) * innerHeight;

  return (
    <div className="chart" ref={ref}>
      <div className="legend" style={{ marginBottom: 6 }}>
        {series.map((item) => (
          <span key={item.key}>
            <span className="swatch" style={{ background: item.color }} /> {item.label}
          </span>
        ))}
      </div>
      <svg width={width} height={height} role="img" aria-label="Model comparison">
        <g transform={`translate(${margin.left},${margin.top})`}>
          {ticks(domainMax).map((value) => (
            <g key={value}>
              <line className="grid-line" x1={0} x2={innerWidth} y1={y(value)} y2={y(value)} />
              <text x={-8} y={y(value) + 4} textAnchor="end" className="num">
                {value.toFixed(2)}
              </text>
            </g>
          ))}
          {categories.map((category, ci) => {
            const start = ci * band + (band - groupWidth) / 2;
            return (
              <g key={category.key}>
                {series.map((item, si) => {
                  const value = item.values[category.key];
                  if (value === null || value === undefined) return null;
                  const x = start + si * (barWidth + 2);
                  const hover = (event: React.PointerEvent | React.FocusEvent) => {
                    const rect = (event.currentTarget as SVGElement).ownerSVGElement!.getBoundingClientRect();
                    const clientX = "clientX" in event ? event.clientX - rect.left : margin.left + x;
                    setTip({
                      x: clientX,
                      y: margin.top + y(value),
                      content: (
                        <>
                          <div className="tt-value">{format(value)}</div>
                          <div className="tt-row">
                            <span className="tt-key" style={{ background: item.color }} /> {item.label}
                          </div>
                          <div className="tt-row">{category.label}</div>
                        </>
                      ),
                    });
                  };
                  return (
                    <g
                      key={item.key}
                      tabIndex={0}
                      onPointerMove={hover}
                      onFocus={hover}
                      onPointerLeave={() => setTip(null)}
                      onBlur={() => setTip(null)}
                    >
                      <rect x={x - 1} y={0} width={barWidth + 2} height={innerHeight} fill="transparent" />
                      <path d={columnPath(x, y(value), barWidth, innerHeight - y(value))} fill={item.color} />
                    </g>
                  );
                })}
                <text x={ci * band + band / 2} y={innerHeight + 18} textAnchor="middle" style={{ fontSize: 11.5 }}>
                  {category.label}
                </text>
              </g>
            );
          })}
          <line className="axis-line" x1={0} x2={innerWidth} y1={innerHeight} y2={innerHeight} />
        </g>
      </svg>
      <Tooltip state={tip} width={width} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Contribution chart: how each factor moved this customer's score
// ---------------------------------------------------------------------------

export function ContributionChart({
  items,
  baseline,
  finalScore,
  valueText,
}: {
  items: Contribution[];
  baseline: number;
  finalScore: number;
  valueText: (item: Contribution) => string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [tip, setTip] = useState<TooltipState | null>(null);
  const shown = items.filter((item) => Math.abs(item.impact) >= 0.5).slice(0, 10);
  const hidden = items.length - shown.length;
  const rowHeight = 30;
  const labelWidth = Math.min(250, Math.max(130, width * 0.4));
  const valueWidth = 52;
  const half = Math.max(40, (width - labelWidth - valueWidth * 2) / 2);
  const zero = labelWidth + valueWidth + half;
  const max = Math.max(...shown.map((item) => Math.abs(item.impact)), 1);
  const height = shown.length * rowHeight + 4;

  return (
    <div className="chart" ref={ref}>
      <div className="legend" style={{ marginBottom: 8 }}>
        <span>
          <span className="swatch" style={{ background: "var(--raise)" }} /> Raises the score
        </span>
        <span>
          <span className="swatch" style={{ background: "var(--lower)" }} /> Lowers the score
        </span>
        <span className="muted">
          Typical legitimate customer {baseline.toFixed(0)} → this customer {finalScore}
        </span>
      </div>
      {shown.length === 0 ? (
        <p className="muted small">No factor moved this score by more than half a point.</p>
      ) : (
        <svg width={width} height={height} role="img" aria-label="Factors behind the risk score">
          <line x1={zero} x2={zero} y1={0} y2={height} stroke="var(--axis)" />
          {shown.map((item, index) => {
            const y = index * rowHeight;
            const length = (Math.abs(item.impact) / max) * half;
            const up = item.impact > 0;
            const hover = (event: React.PointerEvent | React.FocusEvent) => {
              const rect = (event.currentTarget as SVGElement).ownerSVGElement!.getBoundingClientRect();
              const clientX = "clientX" in event ? event.clientX - rect.left : zero;
              setTip({
                x: clientX,
                y,
                content: (
                  <>
                    <div className="tt-value">
                      {up ? "+" : "−"}
                      {Math.abs(item.impact).toFixed(1)} points
                    </div>
                    <div className="tt-row">{item.label}</div>
                    <div className="tt-row">Value: {valueText(item)}</div>
                  </>
                ),
              });
            };
            return (
              <g
                key={item.feature}
                tabIndex={0}
                onPointerMove={hover}
                onFocus={hover}
                onPointerLeave={() => setTip(null)}
                onBlur={() => setTip(null)}
              >
                <rect x={0} y={y} width={width} height={rowHeight} fill="transparent" />
                <text x={labelWidth - 8} y={y + rowHeight / 2 + 4} textAnchor="end" style={{ fill: "var(--text-2)", fontSize: 12 }}>
                  {item.label.length > 36 ? `${item.label.slice(0, 35)}…` : item.label}
                </text>
                <text x={labelWidth} y={y + rowHeight / 2 + 4} className="num" style={{ fill: "var(--muted)", fontSize: 11.5 }}>
                  {valueText(item)}
                </text>
                <path
                  d={
                    up
                      ? barPathRight(zero + 1, y + 7, Math.max(length, 1.5), rowHeight - 14)
                      : barPathLeft(zero - 1, y + 7, Math.max(length, 1.5), rowHeight - 14)
                  }
                  fill={up ? "var(--raise)" : "var(--lower)"}
                />
                <text
                  x={up ? zero + length + 6 : zero - length - 6}
                  y={y + rowHeight / 2 + 4}
                  textAnchor={up ? "start" : "end"}
                  className="num"
                  style={{ fill: "var(--text-2)" }}
                >
                  {up ? "+" : "−"}
                  {Math.abs(item.impact).toFixed(1)}
                </text>
              </g>
            );
          })}
        </svg>
      )}
      {hidden > 0 && <p className="muted small">{hidden} smaller factors not shown.</p>}
      <Tooltip state={tip} width={width} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Utilization timeline
// ---------------------------------------------------------------------------

const EVENT_NAMES: Record<string, string> = {
  account_opened: "Account opened",
  purchase: "Purchase",
  payment: "Payment",
  credit_limit_increase: "Credit-limit increase",
  bust_out_spike: "Large purchase spike",
  large_purchase: "Large purchase",
  account_closed_or_abandoned: "Account closed / abandoned",
  account_closed: "Account closed",
};

export function eventName(type: string): string {
  return EVENT_NAMES[type] ?? type.replace(/_/g, " ");
}

export function UtilizationTimeline({ events }: { events: EventRow[] }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [tip, setTip] = useState<TooltipState | null>(null);
  const [cross, setCross] = useState<number | null>(null);
  const withValue = events.filter((event) => event.utilization !== null);
  const hasUtilization = withValue.length > 0;
  const height = 200;
  const margin = { top: 10, right: 14, bottom: 28, left: 40 };
  const innerWidth = Math.max(100, width - margin.left - margin.right);
  const innerHeight = height - margin.top - margin.bottom;
  const times = events.map((event) => new Date(event.event_date).getTime());
  const minTime = Math.min(...times);
  const maxTime = Math.max(...times);
  const span = Math.max(maxTime - minTime, 86_400_000);
  const sx = (time: number) => ((time - minTime) / span) * innerWidth;
  const sy = (value: number) => innerHeight - Math.min(1, Math.max(0, value)) * innerHeight;
  const points = events.map((event, index) => ({
    x: sx(times[index]),
    y: hasUtilization && event.utilization !== null ? sy(event.utilization) : innerHeight / 2,
    event,
  }));
  const line = points
    .filter((point) => point.event.utilization !== null)
    .map((point, index) => `${index ? "L" : "M"}${point.x},${point.y}`)
    .join(" ");
  const monthTicks: number[] = [];
  const start = new Date(minTime);
  const cursor = new Date(start.getFullYear(), start.getMonth() + 1, 1);
  while (cursor.getTime() <= maxTime) {
    monthTicks.push(cursor.getTime());
    cursor.setMonth(cursor.getMonth() + 3);
  }

  const move = (event: React.PointerEvent<SVGRectElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    let best = 0;
    for (let index = 1; index < points.length; index += 1) {
      if (Math.abs(points[index].x - x) < Math.abs(points[best].x - x)) best = index;
    }
    const point = points[best];
    setCross(best);
    setTip({
      x: margin.left + point.x,
      y: margin.top + point.y,
      content: (
        <>
          <div className="tt-value">
            {point.event.utilization !== null ? `${pct(point.event.utilization)} utilization` : eventName(point.event.event_type)}
          </div>
          <div className="tt-row">
            {eventName(point.event.event_type)} · {point.event.event_date}
          </div>
          {point.event.credit_limit !== null && (
            <div className="tt-row">Credit limit {point.event.credit_limit.toLocaleString()}</div>
          )}
        </>
      ),
    });
  };

  if (events.length === 0) return <p className="muted small">No account events for this customer.</p>;
  const spikeTypes = new Set(["bust_out_spike", "large_purchase", "account_closed_or_abandoned", "account_closed"]);

  return (
    <div className="chart" ref={ref}>
      <div className="legend" style={{ marginBottom: 6 }}>
        {hasUtilization && (
          <span>
            <span className="tt-key" style={{ background: "var(--series-1)", width: 14 }} /> Credit utilization
          </span>
        )}
        <span>
          <span className="ring-swatch" style={{ background: "var(--risk-high)", width: 9, height: 9 }} /> Spike / closure event
        </span>
      </div>
      <svg width={width} height={height} role="img" aria-label="Credit utilization over time">
        <g transform={`translate(${margin.left},${margin.top})`}>
          {hasUtilization &&
            [0, 0.25, 0.5, 0.75, 1].map((value) => (
              <g key={value}>
                <line className="grid-line" x1={0} x2={innerWidth} y1={sy(value)} y2={sy(value)} />
                <text x={-8} y={sy(value) + 4} textAnchor="end" className="num">
                  {value * 100}%
                </text>
              </g>
            ))}
          {monthTicks.map((time) => (
            <text key={time} x={sx(time)} y={innerHeight + 18} textAnchor="middle" className="num">
              {new Date(time).toLocaleDateString(undefined, { month: "short", year: "2-digit" })}
            </text>
          ))}
          <line className="axis-line" x1={0} x2={innerWidth} y1={innerHeight} y2={innerHeight} />
          {hasUtilization && (
            <path d={line} fill="none" stroke="var(--series-1)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          )}
          {points.map((point, index) =>
            spikeTypes.has(point.event.event_type) ? (
              <circle
                key={index}
                cx={point.x}
                cy={point.y}
                r={4.5}
                fill="var(--risk-high)"
                stroke="var(--surface)"
                strokeWidth={2}
              />
            ) : null,
          )}
          {cross !== null && points[cross] && (
            <>
              <line x1={points[cross].x} x2={points[cross].x} y1={0} y2={innerHeight} stroke="var(--axis)" />
              <circle cx={points[cross].x} cy={points[cross].y} r={4.5} fill="var(--series-1)" stroke="var(--surface)" strokeWidth={2} />
            </>
          )}
          <rect
            x={0}
            y={0}
            width={innerWidth}
            height={innerHeight}
            fill="transparent"
            onPointerMove={move}
            onPointerLeave={() => {
              setTip(null);
              setCross(null);
            }}
          />
        </g>
      </svg>
      <Tooltip state={tip} width={width} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Confusion matrix
// ---------------------------------------------------------------------------

export function ConfusionMatrix({ tn, fp, fn, tp }: { tn: number; fp: number; fn: number; tp: number }) {
  const max = Math.max(tn, fp, fn, tp, 1);
  const cell = (value: number, label: string, good: boolean) => (
    <td
      style={{
        background: `color-mix(in srgb, var(--series-1) ${Math.round(8 + (Math.sqrt(value) / Math.sqrt(max)) * 42)}%, var(--surface))`,
        textAlign: "center",
        padding: "14px 10px",
      }}
    >
      <div style={{ fontSize: 20, fontWeight: 650 }} className="num">
        {value.toLocaleString()}
      </div>
      <div className="small" style={{ color: good ? "var(--text-2)" : "var(--critical-ink)" }}>
        {label}
      </div>
    </td>
  );
  return (
    <table className="data" style={{ tableLayout: "fixed" }}>
      <thead>
        <tr>
          <th />
          <th style={{ textAlign: "center" }}>Predicted legitimate</th>
          <th style={{ textAlign: "center" }}>Predicted fraud</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th>Actually legitimate</th>
          {cell(tn, "correctly cleared", true)}
          {cell(fp, "false alarms", false)}
        </tr>
        <tr>
          <th>Actually fraud</th>
          {cell(fn, "missed fraud", false)}
          {cell(tp, "fraud caught", true)}
        </tr>
      </tbody>
    </table>
  );
}
