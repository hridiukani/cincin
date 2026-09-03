import type { Metadata } from "next";
import { Merriweather, Playfair_Display } from "next/font/google";
import "./globals.css";

const merriweather = Merriweather({
  subsets: ["latin"],
  weight: ["300", "400", "700", "900"],
  variable: "--font-merriweather",
});

const playfair = Playfair_Display({
  subsets: ["latin"],
  style: ["italic"],
  variable: "--font-playfair",
});

export const metadata: Metadata = {
  title: "Cincin: Phoenix Happy Hour Finder",
  description: "Find happy hours near you in Phoenix, AZ, in real time.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${merriweather.variable} ${playfair.variable} font-sans antialiased bg-background text-text-primary`}
      >
        {children}
      </body>
    </html>
  );
}
