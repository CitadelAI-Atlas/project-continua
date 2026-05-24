export default function About() {
  return (
    <div>
      <h1 className="text-4xl font-bold mb-4">About</h1>

      <p className="text-zinc-700 dark:text-zinc-300 mb-4">
        Project Continua is building a small vocabulary of audio primitives
        whose meaning is grounded in shared mathematics and acoustic physics.
        The work runs along two complementary tracks:
      </p>

      <ul className="list-disc list-inside space-y-2 text-zinc-700 dark:text-zinc-300 mb-6">
        <li>
          <strong>Track A: teach humans this language.</strong> Use math-native
          audio as a medium humans can learn to perceive, internalize, and use
          fluently. Pedagogy and curriculum design built around the core
          primitives, validated with human-listener studies.
        </li>
        <li>
          <strong>Track B: build it as an efficient codec.</strong> Math-native
          encoding as a high-density, low-overhead channel for transmitting
          rich data via audio. Engineering work on bits-per-second,
          noise-robustness, and integration into real applications.
        </li>
      </ul>

      <h2 className="text-2xl font-semibold mt-8 mb-3">Lineage</h2>

      <p className="text-zinc-700 dark:text-zinc-300 mb-4">
        Pythagorean music-as-math; Hans Freudenthal&apos;s{" "}
        <em>Lincos</em> (1960); SETI / METI; contemporary research on
        receiver-derivable mathematical encodings.
      </p>

      <h2 className="text-2xl font-semibold mt-8 mb-3">Contact</h2>

      <p className="text-zinc-700 dark:text-zinc-300">
        The code is on{" "}
        <a
          href="https://github.com/CitadelAI-Atlas/project-continua"
          className="text-blue-600 dark:text-blue-400 underline"
        >
          GitHub
        </a>
        . File issues or suggestions there.
      </p>
    </div>
  );
}
