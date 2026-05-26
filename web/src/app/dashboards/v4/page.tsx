import V4Dashboard from "@/components/V4Dashboard";

export const metadata = {
  title: "v4 study and test | Project Continua",
  description:
    "Seven receiver-derivable math-native primitives in an interactive Learn / Test / History dashboard. Free-response answers via typing or speech-to-text.",
};

export default function V4DashboardPage() {
  return (
    <div>
      <div className="mb-2 text-sm text-zinc-500">Dashboards / v4</div>
      <h1 className="text-3xl font-bold mb-3">v4 study and test</h1>
      <p className="text-zinc-700 dark:text-zinc-300 mb-2">
        Seven primitives from the current canonical vocabulary, the ones
        established as cross-model derivable in the v4.4 and v4.5 work:
        COUNT, PERIOD, RATIO, BECOMES, AND, IMPLIES_MULTI, FUNCTION_MULTI.
        Each one is the literal mathematical operation made audible.
      </p>
      <p className="text-zinc-700 dark:text-zinc-300 mb-2">
        Use <strong>Learn</strong> to walk through a seven-lesson curriculum.
        Use <strong>Test</strong> to take a randomized blind session in either
        multiple-choice or free-response mode. Free-response accepts typed
        answers or your spoken voice via the browser&apos;s speech-to-text.
        Use <strong>History</strong> to track your cumulative accuracy.
      </p>
      <p className="text-xs text-zinc-500 mb-4">
        Audio examples are pre-rendered .wavs from the v4 and v4.5 renderers.
        Headphones recommended. Speech input requires microphone permission
        and a browser with the Web Speech API (Chrome, Edge, Safari).
      </p>
      <V4Dashboard />
    </div>
  );
}
