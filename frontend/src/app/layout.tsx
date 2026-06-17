import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Due Diligence Copilot",
  description:
    "AI-powered due diligence platform for investment analysis. Upload documents, get instant risk assessments, financial analysis, and executive summaries.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
