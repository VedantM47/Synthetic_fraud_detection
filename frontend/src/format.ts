import type { RiskLevel } from "./api";

export const ATTRIBUTE_LABELS: Record<string, string> = {
  phone: "Phone",
  email: "Email",
  address: "Address",
  device: "Device",
  ip: "IP address",
  national_id: "National ID",
  bank_account: "Bank account",
  identifier: "Identifier",
};

export const ATTRIBUTE_SHORT: Record<string, string> = {
  phone: "phone",
  email: "email",
  address: "addr",
  device: "device",
  ip: "IP",
  national_id: "ID",
  bank_account: "bank",
  identifier: "id",
};

export const GROUP_LABELS: Record<string, string> = {
  tabular: "Profile",
  network: "Network",
  temporal: "Behaviour",
};

export const EXPERIMENT_LABELS: Record<string, string> = {
  tabular: "Profile only",
  tabular_network: "Profile + network",
  tabular_temporal: "Profile + behaviour",
  network: "Network only",
  temporal: "Behaviour only",
  combined: "All features",
};

export const MODEL_LABELS: Record<string, string> = {
  random_forest: "Random Forest",
  hist_gradient_boosting: "Gradient Boosting",
};

export const LEVEL_LABELS: Record<RiskLevel, string> = { high: "High", medium: "Medium", low: "Low" };

export function attributeLabel(kind: string): string {
  return ATTRIBUTE_LABELS[kind] ?? kind.replace(/_/g, " ");
}

export function score(risk: number): number {
  return Math.round(risk * 100);
}

export function pct(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  return `${(value * 100).toFixed(digits)}%`;
}

export function num(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  return value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function compact(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 10_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString();
}

export function dec(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  return value.toFixed(digits);
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "–";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function shortId(id: string, length = 10): string {
  return id.length > length + 2 ? `${id.slice(0, length)}…` : id;
}

export function plural(count: number, word: string, pluralWord?: string): string {
  return `${count.toLocaleString()} ${count === 1 ? word : pluralWord ?? `${word}s`}`;
}

export function featureValue(feature: string, value: number): string {
  if (feature.includes("utilization")) return pct(value);
  if (Number.isInteger(value)) return value.toLocaleString();
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function modeLabel(mode: string): string {
  return mode === "supervised" ? "Trained on your labels" : "Reference model (no labels needed)";
}
