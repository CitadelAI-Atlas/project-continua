import V1Dashboard from "@/components/V1Dashboard";

export const metadata = {
  title: "v1 dashboard | Project Continua",
  description:
    "Eight physical primitives in an interactive study-and-test dashboard. Audio synthesizes in your browser.",
};

export default function V1DashboardPage() {
  return (
    <div>
      <div className="mb-2 text-sm text-zinc-500">Dashboards / v1</div>
      <h1 className="text-3xl font-bold mb-3">v1 study and test</h1>
      <p className="text-zinc-700 dark:text-zinc-300 mb-2">
        An eight-symbol vocabulary of physical primitives. Each one is encoded
        from physical principles (frequency, rhythm, envelope) rather than
        arbitrary mapping.
      </p>
      <p className="text-zinc-700 dark:text-zinc-300 mb-2">
        Use <strong>Learn</strong> to hear each primitive with its rationale.
        Use <strong>Test</strong> for a randomized blind trial sequence with
        binomial scoring against the 12.5% chance baseline. Use{" "}
        <strong>History</strong> to see how your accuracy changes across
        sessions.
      </p>
      <p className="text-xs text-zinc-500 mb-4">
        Audio synthesizes in your browser using the Web Audio API. Headphones
        recommended.
      </p>
      <V1Dashboard />
    </div>
  );
}
