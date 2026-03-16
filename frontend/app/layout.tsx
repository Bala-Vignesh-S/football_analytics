import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Football Analytics — AI Offside & Match Intelligence",
  description: "Real-time football analytics with AI-powered offside detection, player tracking, and club manager portals.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
