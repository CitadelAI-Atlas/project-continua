// Most-recent first. New dashboards land at the TOP of this list.
const dashboards = [
  {
    href: "/dashboards/v2",
    title: "v2 study and test",
    blurb:
      "Twenty math-native primitives grouped by category: quantity, operator, relation, logic, quantifier, reference, process. Each is defined by a mathematical structure rendered as its exact acoustic realization.",
    available: true,
  },
  {
    href: "/dashboards/v1",
    title: "v1 study and test",
    blurb:
      "Eight physical primitives. Listen in study mode, then take a randomized blind test. Binomial significance scoring against the 12.5% chance baseline.",
    available: true,
  },
];

export default function DashboardsIndex() {
  return (
    <div>
      <h1 className="text-4xl font-bold mb-4">Dashboards</h1>
      <p className="text-zinc-700 dark:text-zinc-300 mb-6">
        Interactive tools for hearing and learning the math-native vocabulary.
        Audio runs entirely in your browser, no server round-trips. Most
        recent at the top.
      </p>
      <div className="space-y-3">
        {dashboards.map((d) =>
          d.available ? (
            <a
              key={d.href}
              href={d.href}
              className="block rounded-lg border border-zinc-200 dark:border-zinc-800 p-4 hover:border-blue-400 dark:hover:border-blue-600 transition"
            >
              <div className="font-semibold">{d.title}</div>
              <div className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">
                {d.blurb}
              </div>
            </a>
          ) : (
            <div
              key={d.href}
              className="block rounded-lg border border-zinc-200 dark:border-zinc-800 p-4 opacity-60"
            >
              <div className="font-semibold">{d.title}</div>
              <div className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">
                {d.blurb}
              </div>
              <div className="text-xs text-zinc-500 mt-2">Coming soon</div>
            </div>
          )
        )}
      </div>
    </div>
  );
}
