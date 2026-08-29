import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { AppShell } from "@/components/layout/AppShell";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jbMono = JetBrains_Mono({
  variable: "--font-jbmono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SMC Terminal",
  description: "India Adaptive SMC Trading Intelligence Platform — manual execution, Telegram-alerted.",
};

// Runs before paint to apply a stored theme preference without a flash of
// the wrong theme (dark is the CSS default, so this only ever needs to
// react when the stored preference is "light").
const themeInitScript = `
(function () {
  try {
    var stored = window.localStorage.getItem('theme');
    if (stored === 'light') {
      document.documentElement.setAttribute('data-theme', 'light');
    }
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${jbMono.variable} h-full`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-full font-sans antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
