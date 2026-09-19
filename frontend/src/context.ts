import { createContext, useContext } from "react";
import { useOutletContext } from "react-router-dom";
import type { DatasetDetail, DatasetListItem } from "./api";
import type { Theme } from "./hooks";

export interface AppContextValue {
  datasets: DatasetListItem[] | null;
  datasetsError: string | null;
  reloadDatasets: () => void;
  theme: Theme;
  resolvedTheme: "light" | "dark";
  setTheme: (theme: Theme) => void;
}

export const AppContext = createContext<AppContextValue | null>(null);

export function useApp(): AppContextValue {
  const value = useContext(AppContext);
  if (!value) throw new Error("AppContext missing");
  return value;
}

export interface DatasetContextValue {
  dataset: DatasetDetail;
  /** Increments whenever a new model version is saved; pages refetch on change. */
  version: number;
  reloadDataset: () => void;
  startJob: (jobId: string) => void;
}

export function useDataset(): DatasetContextValue {
  return useOutletContext<DatasetContextValue>();
}

export function rememberDataset(id: string): void {
  try {
    localStorage.setItem("lastDataset", id);
  } catch {
    // storage unavailable
  }
}

export function lastDataset(): string | null {
  try {
    return localStorage.getItem("lastDataset");
  } catch {
    return null;
  }
}
