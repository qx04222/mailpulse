import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import LocaleProvider from "@/lib/i18n/provider";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Email Digest Admin",
  description: "Admin panel for the email digest system",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh"
      className={`${geistSans.variable} ${geistMono.variable} h-full`}
    >
      <body className="h-full">
        <LocaleProvider>{children}</LocaleProvider>
      </body>
    </html>
  );
}
