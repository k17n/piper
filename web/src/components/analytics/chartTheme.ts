export interface ChartColors {
  ink: string;
  ink2: string;
  muted: string;
  line: string;
  surface: string;
  accent: string;
}

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
  };
}

export const tooltipStyle = (c: ChartColors) => ({
  backgroundColor: c.surface,
  borderColor: c.line,
  textStyle: { color: c.ink, fontSize: 12 },
  extraCssText: "border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.25);",
});

export const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
