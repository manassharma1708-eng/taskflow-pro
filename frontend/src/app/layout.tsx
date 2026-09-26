import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TaskFlow Pro — Dependency-Aware Kanban Board",
  description:
    "Intelligent project management with DAG-powered dependency tracking, schedule propagation, and AI-assisted workflow optimization.",
  keywords: ["kanban", "project management", "DAG", "dependency tracking", "schedule propagation"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
