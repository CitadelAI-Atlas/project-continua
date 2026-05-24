import type { MDXComponents } from "mdx/types";
import AudioPlayer from "@/components/AudioPlayer";

const components: MDXComponents = {
  h1: ({ children }) => (
    <h1 className="text-4xl font-bold mt-8 mb-4">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-2xl font-semibold mt-8 mb-3">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-xl font-semibold mt-6 mb-2">{children}</h3>
  ),
  p: ({ children }) => <p className="my-3 leading-relaxed">{children}</p>,
  ul: ({ children }) => (
    <ul className="list-disc list-inside my-3 space-y-1">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-inside my-3 space-y-1">{children}</ol>
  ),
  code: ({ children }) => (
    <code className="px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-sm font-mono">
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre className="my-4 p-4 rounded bg-zinc-100 dark:bg-zinc-900 overflow-x-auto text-sm">
      {children}
    </pre>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-4 pl-4 border-l-4 border-zinc-300 dark:border-zinc-700 italic">
      {children}
    </blockquote>
  ),
  table: ({ children }) => (
    <table className="my-4 w-full border-collapse text-sm">{children}</table>
  ),
  th: ({ children }) => (
    <th className="border border-zinc-300 dark:border-zinc-700 px-3 py-2 text-left bg-zinc-50 dark:bg-zinc-800">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-zinc-300 dark:border-zinc-700 px-3 py-2">
      {children}
    </td>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      className="text-blue-600 dark:text-blue-400 underline hover:no-underline"
    >
      {children}
    </a>
  ),
  AudioPlayer,
};

export function useMDXComponents(): MDXComponents {
  return components;
}
