export default function About() {
  return (
    <div>
      <h1 className="text-4xl font-bold mb-4">About</h1>

      <p className="text-zinc-700 dark:text-zinc-300 mb-4">
        Project Continua is an open, iterative investigation of whether
        humans can use more of the sound wave to gain context than text
        or speech currently let them, and whether that channel can help
        us communicate more efficiently with machines. Math-native audio
        is the chosen vocabulary because it is clean, derivable, and
        machine-friendly; the wider claim is about the perceptual
        channel itself.
      </p>

      <h2 className="text-2xl font-semibold mt-8 mb-3">How the work is organized</h2>

      <p className="text-zinc-700 dark:text-zinc-300 mb-4">
        The project runs as a sequence of small, falsifiable probes.
        Each probe is cheap on its own, targets one slice of the larger
        question, and writes up its result regardless of outcome. The
        first probe is a perception study comparing math-structured
        audio against matched plain text and matched synthesized speech
        on the same content, with a parallel set of in-depth interviews.
        Subsequent probes extend to richer stimuli, expert listeners,
        and machine-to-human contextual transfer.
      </p>

      <p className="text-zinc-700 dark:text-zinc-300 mb-4">
        Two engineering threads run alongside the probe sequence and
        share its vocabulary:
      </p>

      <ul className="list-disc list-inside space-y-2 text-zinc-700 dark:text-zinc-300 mb-6">
        <li>
          <strong>Teaching humans this language.</strong> Pedagogy and
          curriculum built around the core primitives, so the
          ear-and-brain perception that finds a string quartet beautiful
          does the work of internalizing the mathematical structure
          beneath it.
        </li>
        <li>
          <strong>Building it as an acoustic codec.</strong>{" "}
          Math-native encoding as a high-density channel for
          transmitting structured data via audio. Engineering on
          bits-per-second, noise-robustness, and integration into real
          applications.
        </li>
      </ul>

      <p className="text-zinc-700 dark:text-zinc-300 mb-6">
        Both engineering threads depend on the same upstream answer.
        Whether the perceptual channel is real, and to whom, is what
        the probe sequence is designed to find out. The threads pause
        new development during a probe and resume with sharper outcomes
        once the probe reports.
      </p>

      <h2 className="text-2xl font-semibold mt-8 mb-3">Lineage</h2>

      <p className="text-zinc-700 dark:text-zinc-300 mb-4">
        Pythagorean music-as-math; Hans Freudenthal&apos;s{" "}
        <em>Lincos</em> (1960); SETI / METI; contemporary research on
        receiver-derivable mathematical encodings; the stenotype
        machine, where a court reporter&apos;s chord-keying inspired the
        project&apos;s framing of simultaneity as bandwidth.
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
