import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function getStatusColor(status: string): string {
  const map: Record<string, string> = {
    complete: "badge-success",
    failed: "badge-danger",
    pending: "badge-neutral",
    extracting: "badge-info",
    chunking: "badge-info",
    embedding: "badge-info",
    running: "badge-info",
    active: "badge-success",
  };
  return map[status] || "badge-neutral";
}

export function getSeverityColor(severity: string): string {
  const s = severity.toLowerCase();
  if (s === "high") return "severity-high";
  if (s === "medium") return "severity-medium";
  return "severity-low";
}
