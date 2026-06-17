/**
 * Tests for utility functions.
 */
import { describe, it, expect } from "vitest";
import {
  formatFileSize,
  formatDate,
  getStatusColor,
  getSeverityColor,
} from "@/lib/utils";

describe("formatFileSize", () => {
  it("formats 0 bytes", () => {
    expect(formatFileSize(0)).toBe("0 B");
  });

  it("formats bytes", () => {
    expect(formatFileSize(500)).toBe("500 B");
  });

  it("formats kilobytes", () => {
    expect(formatFileSize(1024)).toBe("1 KB");
    expect(formatFileSize(2560)).toBe("2.5 KB");
  });

  it("formats megabytes", () => {
    expect(formatFileSize(1048576)).toBe("1 MB");
    expect(formatFileSize(5242880)).toBe("5 MB");
  });

  it("formats gigabytes", () => {
    expect(formatFileSize(1073741824)).toBe("1 GB");
  });
});

describe("formatDate", () => {
  it("formats ISO date string", () => {
    const result = formatDate("2023-12-15T10:30:00Z");
    expect(result).toContain("Dec");
    expect(result).toContain("15");
    expect(result).toContain("2023");
  });
});

describe("getStatusColor", () => {
  it("returns success for complete", () => {
    expect(getStatusColor("complete")).toBe("badge-success");
  });

  it("returns danger for failed", () => {
    expect(getStatusColor("failed")).toBe("badge-danger");
  });

  it("returns info for processing states", () => {
    expect(getStatusColor("extracting")).toBe("badge-info");
    expect(getStatusColor("chunking")).toBe("badge-info");
    expect(getStatusColor("embedding")).toBe("badge-info");
  });

  it("returns neutral for unknown status", () => {
    expect(getStatusColor("unknown")).toBe("badge-neutral");
  });
});

describe("getSeverityColor", () => {
  it("returns correct severity colors", () => {
    expect(getSeverityColor("High")).toBe("severity-high");
    expect(getSeverityColor("Medium")).toBe("severity-medium");
    expect(getSeverityColor("Low")).toBe("severity-low");
  });

  it("is case insensitive", () => {
    expect(getSeverityColor("high")).toBe("severity-high");
    expect(getSeverityColor("HIGH")).toBe("severity-high");
  });
});
