export interface ChartColors {
  ink: string;
  ink2: string;
  muted: string;
  line: string;
  surface: string;
  accent: string;
  shadow: string;
}

// Single quotes: these strings are also embedded in style="…" attributes inside tooltip HTML.
export const MONO = "'Geist Mono Variable', ui-monospace, Consolas, monospace";
export const SANS = "'Geist Variable', system-ui, sans-serif";

/** Read the live theme colours; call inside a memo that depends on `dark` so charts follow the toggle. */
export function chartColors(): ChartColors {
  const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return {
    ink: css("--text"),
    ink2: css("--text-2"),
    muted: css("--muted"),
    line: css("--border"),
    surface: css("--surface"),
    accent: css("--accent"),
    shadow: css("--shadow-pop"),
  };
}

/** `#rrggbb` + opacity → `rgba(...)`. */
export function alpha(hex: string, a: number) {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.replace(/./g, "$&$&") : h, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

const axisLabel = (c: ChartColors, extra: object = {}) => ({ color: c.muted, fontSize: 11, fontFamily: MONO, ...extra });

export const categoryAxis = (c: ChartColors, labels: string[]) => ({
  type: "category" as const,
  data: labels,
  axisLabel: axisLabel(c, { hideOverlap: true }),
  axisLine: { show: false },
  axisTick: { show: false },
});

export const valueAxis = (c: ChartColors, o: { formatter?: string; min?: number; max?: number; minInterval?: number } = {}) => {
  const { formatter, ...rest } = o;
  return {
    type: "value" as const,
    ...rest,
    axisLabel: axisLabel(c, formatter ? { formatter } : {}),
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: { lineStyle: { color: c.line, type: "dotted" as const } },
  };
};

export const tooltipStyle = (c: ChartColors) => ({
  backgroundColor: c.surface,
  borderColor: c.line,
  borderWidth: 1,
  padding: [8, 10],
  textStyle: { color: c.ink, fontSize: 12, fontFamily: SANS },
  extraCssText: `border-radius:8px;box-shadow:${c.shadow};`,
  axisPointer: { lineStyle: { color: c.line, type: "dotted" }, shadowStyle: { color: alpha(c.ink.startsWith("#") ? c.ink : "#888888", 0.05) } },
});

/** Tooltip body: bold title, then rows with an optional colour dot and a right-aligned mono value. Callers escape text. */
export function tip(title: string, rows: { dot?: string; label: string; value?: string }[] = [], note = "") {
  const body = rows
    .map(
      (r) =>
        `<div style="display:flex;align-items:center;gap:8px;margin-top:4px">${
          r.dot ? `<span style="width:8px;height:8px;border-radius:999px;background:${r.dot}"></span>` : ""
        }<span style="flex:1;opacity:.8">${r.label}</span>${
          r.value ? `<span style="font-family:${MONO};margin-left:12px">${r.value}</span>` : ""
        }</div>`,
    )
    .join("");
  return `<div style="font-weight:600">${title}</div>${body}${note ? `<div style="margin-top:6px;opacity:.6">${note}</div>` : ""}`;
}

export const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
