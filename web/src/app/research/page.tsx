// Most-recent first. New versions land at the TOP of this list.
const outputs = [
  {
    href: "/research/v5",
    title: "v5: raw-audio protocol",
    period: "May 2026",
    blurb:
      "Receivers analyze the .wav directly with their own tools, no project-specific analyzer in the loop. Validated on the COUNT primitive.",
  },
  {
    href: "/research/v4-5",
    title: "v4.4 - v4.5: cross-model methodology",
    period: "May 2026",
    blurb:
      "Introduced cross-model testing across Opus, Sonnet, and Haiku; locked in pre-registration and verbatim-prompt practices. Established the seven cross-model-stable primitives.",
  },
  {
    href: "/research/v4",
    title: "v4: receiver-derivable vocabulary",
    period: "May 2026",
    blurb:
      "Reframed the project around derivability without shared spec. Iteratively refined the nine-primitive math-native vocabulary and introduced the multi-instance ostensive technique.",
  },
  {
    href: "/research/v3",
    title: "v3: 4-axis feature space",
    period: "Early-mid 2026",
    blurb:
      "Tested whether richer per-primitive features improved decoding. Clarified that source separation, not feature richness, was the bottleneck.",
  },
  {
    href: "/research/v2",
    title: "v2: 20-primitive chord grammar",
    period: "Early 2026",
    blurb:
      "Made encoding math-native via integer ratios and a three-band chord grammar. Surfaced the encoder/decoder asymmetry that drove the next several rounds.",
  },
  {
    href: "/research/v1",
    title: "v1: 8-symbol proof of concept",
    period: "Early 2026",
    blurb:
      "Established the encoder, dashboard, and statistical scoring pipeline. Eight-symbol vocabulary with physically-grounded encoding.",
  },
];

export default function ResearchIndex() {
  return (
    <div>
      <h1 className="text-4xl font-bold mb-4">Research</h1>
      <p className="text-zinc-700 dark:text-zinc-300 mb-6">
        Each output below describes a step that contributed to where the
        project is today. These are living documents: they get edited as the
        understanding sharpens, so the path stays current. Most recent at the
        top.
      </p>
      <div className="space-y-3">
        {outputs.map((v) => (
          <a
            key={v.href}
            href={v.href}
            className="block rounded-lg border border-zinc-200 dark:border-zinc-800 p-4 hover:border-blue-400 dark:hover:border-blue-600 transition"
          >
            <div className="flex items-baseline justify-between">
              <span className="font-semibold">{v.title}</span>
              <span className="text-xs text-zinc-500">{v.period}</span>
            </div>
            <div className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">
              {v.blurb}
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
