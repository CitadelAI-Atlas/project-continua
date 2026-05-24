import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
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
  title: "Project Continua",
  description:
    "Math-native acoustic communication: a public research log on whether two intelligences sharing only mathematics and physics can communicate via sound.",
};

function Nav() {
  return (
    <nav className="border-b border-zinc-200 dark:border-zinc-800 bg-white/80 dark:bg-zinc-950/80 backdrop-blur sticky top-0 z-10">
      <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
        <a href="/" className="font-semibold tracking-tight text-lg">
          Project Continua
        </a>
        <div className="flex gap-6 text-sm text-zinc-600 dark:text-zinc-400">
          <a href="/vocabulary" className="hover:text-blue-600 dark:hover:text-blue-400">
            Vocabulary
          </a>
          <a href="/about" className="hover:text-blue-600 dark:hover:text-blue-400">
            About
          </a>
          <a
            href="https://github.com/CitadelAI-Atlas/project-continua"
            target="_blank"
            rel="noreferrer"
            className="hover:text-blue-600 dark:hover:text-blue-400"
          >
            GitHub
          </a>
        </div>
      </div>
    </nav>
  );
}

function Footer() {
  return (
    <footer className="mt-16 border-t border-zinc-200 dark:border-zinc-800">
      <div className="max-w-4xl mx-auto px-6 py-8 text-sm text-zinc-500 dark:text-zinc-400">
        <div>
          Project Continua. Public research log. Code at{" "}
          <a
            href="https://github.com/CitadelAI-Atlas/project-continua"
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            github.com/CitadelAI-Atlas/project-continua
          </a>
          .
        </div>
        <div className="mt-1">
          Audio examples are CC-BY (preliminary). Code license TBD.
        </div>
      </div>
    </footer>
  );
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100">
        <Nav />
        <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-8">
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}
