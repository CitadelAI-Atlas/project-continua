export default function Home() {
  return (
    <article className="py-12">
      <header className="mb-12">
        <h1 className="text-5xl font-bold tracking-tight mb-3">
          Project Continua
        </h1>
        <p className="text-lg text-zinc-500 dark:text-zinc-400 italic">
          A language whose sentences are also their own proofs.
        </p>
      </header>

      <div className="prose prose-zinc dark:prose-invert max-w-none space-y-6 text-lg leading-relaxed text-zinc-800 dark:text-zinc-200">
        <p>
          Mathematics is one of the few languages whose statements remain
          true in any universe that contains thought. The circumference of
          a circle is 2&pi;r wherever you measure it. Two and three make
          five regardless of who is counting. If a mind exists capable of
          mathematics at all, these things are known to it; they are not
          opinions, and they do not require translation.
        </p>

        <p>
          Sound is one of mathematics&apos;s most direct physical
          expressions. A vibration at 440 cycles per second is not a
          symbol for the number 440; it is the number 440, alive in the
          displacement of air. When two such vibrations stand in the
          ratio 3:2, your brain hears a perfect fifth, and what your
          auditory cortex is recognizing is arithmetic.
        </p>

        <p>
          Music has always been doing this. In the sixth century BCE,
          Pythagoras divided a string and discovered that the consonant
          intervals were the ones whose lengths formed small whole-number
          ratios; the lasting claim of his school was that beauty and
          mathematics are the same fact in two domains. Kepler heard the
          planets as harmonies, fitting their motions to the same kinds
          of integer ratios that govern a chord (<em>Harmonices Mundi</em>,
          1619). Helmholtz, two centuries later, derived from first
          principles about the ear and the spectrum of a wave why a major
          triad sounds settled and a tritone sounds unstable. A
          mathematical proof and a symphonic phrase are two faces of the
          same coin, both elegant for the same reason: a small set of
          generative rules opening into a vast, lawful space of form.
        </p>

        <p>
          Project Continua takes this lineage as its instruction. We are
          building a small vocabulary of audio primitives whose meaning
          is not a label sitting on top of the sound but is the sound&apos;s
          mathematical structure itself. The integer two is two
          simultaneous tones at a 2:1 ratio. The relation <em>greater than</em> is
          a rising pitch. A continuous transformation is a glide.
          Multiplication is amplitude modulation. Periodicity is a pulse
          that returns at a fixed interval. The primitives compose the
          way notes compose, and a receiver who shares only mathematics
          and acoustic physics with the sender can derive what the audio
          means because the audio <em>is</em> the meaning.
        </p>

        <p>
          The name is a deliberate echo. A continuum is what holds
          together without breaks: the real number line, a sustained
          tone, the unbroken arc of meaning between two minds that share
          a substrate. <em>Continua</em>, plural, points at the several
          lines on which this work runs at once: between mathematics and
          its physical expression, between music and proof, between
          sender and receiver. The closest direct ancestor is Hans
          Freudenthal&apos;s <em>Lincos</em> (1960), an attempt at a
          fully decodable mathematical language for communication across
          minds. This project descends from that tradition, in the
          specific medium of audio, with the contemporary means to test
          whether the receiver actually decodes what the sender encoded.
        </p>

        <p>
          There are two ways forward, and we are pursuing both. The first
          is to teach humans this language and let the same ear-and-brain
          perception that finds the third movement of a string quartet
          beautiful do the work of internalizing the mathematical
          structure beneath it. The second is to use the vocabulary as a
          high-density acoustic codec, where two systems that share the
          mathematics share the channel by construction. Pedagogy on one
          side; engineering on the other; the same continuum running
          through both.
        </p>
      </div>

      <section className="mt-16 pt-10 border-t border-zinc-200 dark:border-zinc-800">
        <div className="grid sm:grid-cols-3 gap-4">
          <a
            href="/vocabulary"
            className="block rounded-lg border border-zinc-200 dark:border-zinc-800 p-5 hover:border-blue-400 dark:hover:border-blue-600 transition"
          >
            <div className="font-semibold mb-1">Hear the vocabulary</div>
            <div className="text-sm text-zinc-600 dark:text-zinc-400">
              Playable primitives in your browser.
            </div>
          </a>
          <a
            href="/dashboards"
            className="block rounded-lg border border-zinc-200 dark:border-zinc-800 p-5 hover:border-blue-400 dark:hover:border-blue-600 transition"
          >
            <div className="font-semibold mb-1">Open the dashboards</div>
            <div className="text-sm text-zinc-600 dark:text-zinc-400">
              Study and blind-test the primitives.
            </div>
          </a>
          <a
            href="/research"
            className="block rounded-lg border border-zinc-200 dark:border-zinc-800 p-5 hover:border-blue-400 dark:hover:border-blue-600 transition"
          >
            <div className="font-semibold mb-1">Read the research</div>
            <div className="text-sm text-zinc-600 dark:text-zinc-400">
              The path of work that led here.
            </div>
          </a>
        </div>
      </section>
    </article>
  );
}
