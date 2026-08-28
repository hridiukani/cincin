import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Cincin — Phoenix Happy Hour Finder",
  description: "Find happy hours near you in Phoenix, AZ, in real time.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} font-sans antialiased bg-background text-text-primary`}>
        <header className="sticky top-0 z-50 h-[57px] flex items-center justify-between px-4 md:px-6 bg-background border-b border-border">
          <span className="text-xl font-bold text-primary tracking-tight">Cincin</span>
          <span className="hidden md:block text-sm text-text-muted">Phoenix deals, found.</span>
        </header>
        {children}
      </body>
    </html>
  );
}
