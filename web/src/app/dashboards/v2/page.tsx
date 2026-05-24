import V2Dashboard from "@/components/V2Dashboard";

export const metadata = {
  title: "v2 dashboard | Project Continua",
  description:
    "Twenty math-native primitives in an interactive study-and-test dashboard. Audio synthesizes in your browser.",
};

export default function V2DashboardPage() {
  return (
    <div>
      <div className="mb-2 text-sm text-zinc-500">Dashboards / v2</div>
      <h1 className="text-3xl font-bold mb-3">v2 study and test</h1>
      <p className="text-zinc-700 dark:text-zinc-300 mb-2">
        Twenty math-native primitives grouped by category. Each one is defined
        by a mathematical structure (frequency ratio, wave transformation,
        temporal pattern) rendered as its exact acoustic realization.
      </p>
      <p className="text-zinc-700 dark:text-zinc-300 mb-2">
        Use <strong>Learn</strong> to explore the vocabulary by category.
        Use <strong>Test</strong> to take a randomized blind trial over the
        16 testable primitives, scored against the {(100 / 16).toFixed(1)}%
        chance baseline. Use <strong>History</strong> to track your
        cumulative learning curve.
      </p>
      <p className="text-xs text-zinc-500 mb-4">
        Audio synthesizes in your browser using the Web Audio API. Headphones
        recommended.
      </p>
      <V2Dashboard />
    </div>
  );
}
