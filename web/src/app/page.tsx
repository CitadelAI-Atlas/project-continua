export default function Home() {
  return (
    <div>
      <section className="py-12">
        <h1 className="text-5xl font-bold tracking-tight mb-4">
          Project Continua
        </h1>
        <p className="text-xl text-zinc-700 dark:text-zinc-300 leading-relaxed mb-6">
          Math-native acoustic communication. Audio designed so that the math
          IS the meaning, not a label on top of it.
        </p>
        <p className="text-zinc-700 dark:text-zinc-300 leading-relaxed">
          A small vocabulary of primitives grounded in shared mathematics and
          acoustic physics: integer frequency ratios, periodic timing,
          continuous transformation, co-presence, ordered sequence. The
          primitives compose into higher-level statements the way notes
          compose into chords or words into sentences.
        </p>
      </section>

      <section className="py-8">
        <h2 className="text-2xl font-semibold mb-4">Two tracks</h2>
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-5">
            <h3 className="font-semibold mb-2">
              Track A: teach humans this language
            </h3>
            <p className="text-sm text-zinc-700 dark:text-zinc-300">
              Use math-native audio as a medium humans can learn to perceive,
              internalize, and use fluently.
            </p>
          </div>
          <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-5">
            <h3 className="font-semibold mb-2">
              Track B: build it as an efficient codec
            </h3>
            <p className="text-sm text-zinc-700 dark:text-zinc-300">
              Math-native encoding as a high-density, low-overhead channel
              for transmitting rich data via audio.
            </p>
          </div>
        </div>
      </section>

      <section className="py-8">
        <h2 className="text-2xl font-semibold mb-4">Try it</h2>
        <p className="text-zinc-700 dark:text-zinc-300 mb-4">
          The vocabulary is playable in your browser, and the dashboards run
          a full study-and-test flow with blind scoring. Headphones recommended.
        </p>
        <div className="flex flex-wrap gap-3">
          <a
            href="/vocabulary"
            className="inline-block px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium transition"
          >
            Hear the vocabulary
          </a>
          <a
            href="/dashboards"
            className="inline-block px-5 py-2.5 rounded-lg border border-zinc-300 dark:border-zinc-700 hover:border-blue-400 dark:hover:border-blue-600 font-medium transition"
          >
            Open the dashboards
          </a>
        </div>
      </section>

      <section className="py-8">
        <h2 className="text-2xl font-semibold mb-4">How we got here</h2>
        <p className="text-zinc-700 dark:text-zinc-300 mb-4">
          Each research output below describes a baby step that contributed
          to the current vocabulary and the dual-track program. Living
          documents, edited as understanding sharpens. Most recent first.
        </p>
        <a
          href="/research"
          className="inline-block px-5 py-2.5 rounded-lg border border-zinc-300 dark:border-zinc-700 hover:border-blue-400 dark:hover:border-blue-600 font-medium transition"
        >
          Read the research
        </a>
      </section>

      <section className="py-8">
        <h2 className="text-2xl font-semibold mb-4">Lineage</h2>
        <p className="text-zinc-700 dark:text-zinc-300">
          Pythagorean music-as-math; Hans Freudenthal&apos;s{" "}
          <em>Lincos</em> (1960); SETI / METI; contemporary research on
          receiver-derivable mathematical encodings.
        </p>
      </section>
    </div>
  );
}
