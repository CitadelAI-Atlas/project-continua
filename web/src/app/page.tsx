export default function Home() {
  return (
    <article className="py-8 sm:py-12">
      <header className="mb-8 sm:mb-12">
        <h1 className="text-3xl sm:text-5xl font-bold tracking-tight mb-3">
          Project Continua
        </h1>
        <p className="text-base sm:text-lg text-zinc-500 dark:text-zinc-400 italic">
          A language whose sentences are also their own proofs.
        </p>
      </header>

      <div className="prose prose-zinc dark:prose-invert max-w-none space-y-5 sm:space-y-6 text-base sm:text-lg leading-relaxed text-zinc-800 dark:text-zinc-200">
        <p>
          Mathematics is one of the few languages whose statements remain
          true in any universe that contains thought. The circumference of
          a circle is 2&pi;r wherever you measure it. Two and three make
          five regardless of who is counting. If a mind exists capable of
          mathematics at all, these things are known to it. They are not
          opinions, and they do not require translation.
        </p>

        <p>
          Sound is one of mathematics&apos;s most direct physical
          expressions. A vibration at 440 cycles per second is the number
          440, alive in the displacement of air. When two such vibrations
          stand in the ratio 3:2, your brain hears a perfect fifth:
          arithmetic, recognized by the auditory cortex.
        </p>

        <p>
          Music has always done this. Twenty-five centuries ago Pythagoras
          divided a string and found that the consonant intervals were
          the ones whose lengths formed small whole-number ratios. Kepler
          fit the planets&apos; motions to the same kinds of integer
          ratios that govern a chord (<em>Harmonices Mundi</em>, 1619).
          Helmholtz derived from first principles why a major triad sounds
          settled and a tritone sounds unstable. A mathematical proof
          and a symphonic phrase are two faces of the same coin: a small
          set of generative rules opening into a vast, lawful space of
          form.
        </p>

        <p>
          A second lineage matters here, less famous than music but
          closer to the engineering point. A court reporter writes at the
          speed of speech because the stenotype machine keys chords, not
          letters. Pressing several keys at the same instant names a
          syllable or word as a single event in time. The bandwidth is
          in the simultaneity. The same insight applies to sound: a
          single moment can carry several superposed tones, each
          contributing structure, and a listener who knows how to read
          them recovers more in that moment than any serial sequence of
          labels could deliver.
        </p>

        <p>
          Project Continua builds a small vocabulary of audio primitives
          whose meaning is the sound&apos;s mathematical structure
          itself. The integer two is two simultaneous tones at a 2:1
          ratio. The relation <em>greater than</em> is a rising pitch.
          A continuous transformation is a glide. Periodicity is a pulse
          that returns at a fixed interval. The primitives compose the
          way notes compose, and a receiver who shares only mathematics
          and acoustic physics with the sender can derive what the audio
          means because the audio <em>is</em> the meaning.
        </p>

        <p>
          The name is a deliberate echo. A continuum holds together
          without breaks: the real number line, a sustained tone, the
          unbroken arc of meaning between two minds that share a
          substrate. <em>Continua</em>, plural, points at the several
          lines on which this work runs at once. The closest direct
          ancestor is Hans Freudenthal&apos;s <em>Lincos</em> (1960), an
          attempt at a fully decodable mathematical language for
          communication across minds.
        </p>

        <p>
          There are two ways forward. The first is to teach humans this
          language so the ear-and-brain perception that finds a string
          quartet beautiful does the work of internalizing the
          mathematical structure beneath it. The second is to use the
          vocabulary as a high-density acoustic codec, where two systems
          sharing the mathematics share the channel by construction.
          Listening on one side, engineering on the other; the same
          continuum running through both.
        </p>

        <p>
          The vocabulary itself is an ongoing research artifact. It
          stays small on purpose because every primitive has to clear
          the same bar (a receiver who shares only mathematics and
          acoustic physics can derive its meaning from the audio
          alone), and it grows when a piece of math we want to express
          isn&apos;t reachable from the current set. The current
          primitives cover counting, ratios, continuous transformation,
          simultaneity, sequence, periodicity, and the multi-instance
          forms of implication and functional mapping. Enough to express
          small statements; not yet enough to carry a calculus proof
          end to end. Most of the expressive range comes from
          composition: the way arithmetic uses a handful of operators
          to reach the infinite, our handful of primitives nests to
          reach what the channel needs to carry.
        </p>

        <p>
          The unifying goal is a more efficient path for humans and
          machines to communicate. Today even a short mathematical
          statement has to be spelled out in a natural language and
          parsed at the receiving end, with a translation step in
          between that wastes both time and accuracy. The vocabulary on
          this site removes that step at the bottom of the stack: when
          the sentence is the sound&apos;s mathematical structure
          itself, sender and receiver meet at the level both already
          share. Faster for machines, learnable for humans, one channel
          for both. The long arc is a vocabulary rich enough, and
          listeners practiced enough, that two minds sharing only
          mathematics could carry on a real conversation through this
          channel.
        </p>

        <p>
          One personal note. In a high school geometry class many years
          ago, I worked out a small theorem in plane geometry about the
          angles within certain figures, one that neither I nor my
          teacher could find anywhere else. This was before search
          engines made checking that kind of thing trivial; verifying
          whether a result was already known meant going to a library
          and not finding what you were looking for. My teacher
          accepted the proof on its merits and let my classmates and me
          use what we called the Rich Drye theorem on certain exam
          problems. That was the full extent of its life. I never wrote
          it up for publication, even though my teacher begged me to.
          The daily texture of being a high schooler absorbed my
          attention, and over the years the theorem faded out of
          memory. I am old enough now to recognize a small loss for
          what it is. This site is, in part, a commitment to not let
          that kind of loss happen again. We are documenting the
          journey in public as it goes, so the next idea worth keeping
          does not get the same fate.
        </p>
      </div>

      <aside className="mt-12 pt-8 border-t border-zinc-200 dark:border-zinc-800">
        <a
          href="https://www.linkedin.com/in/richarddrye"
          target="_blank"
          rel="noopener noreferrer"
          className="group inline-flex items-center gap-3"
          aria-label="Richard Drye on LinkedIn"
        >
          <span className="flex h-10 w-10 items-center justify-center rounded-md bg-[#0A66C2] text-white shadow-sm transition group-hover:bg-[#004182]">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              aria-hidden="true"
              className="h-5 w-5 fill-current"
            >
              <path d="M20.45 20.45h-3.55v-5.57c0-1.33-.02-3.04-1.85-3.04-1.86 0-2.14 1.45-2.14 2.95v5.66H9.36V9h3.41v1.56h.05c.47-.9 1.63-1.85 3.36-1.85 3.6 0 4.27 2.37 4.27 5.45v6.29zM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13zM7.12 20.45H3.56V9h3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.72v20.56C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.72V1.72C24 .77 23.2 0 22.22 0z" />
            </svg>
          </span>
          <span className="flex flex-col leading-tight">
            <span className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
              Author and lead developer
            </span>
            <span className="font-semibold text-zinc-900 dark:text-zinc-100 transition group-hover:text-[#0A66C2] dark:group-hover:text-[#4593e6]">
              Richard Drye
            </span>
          </span>
        </a>
      </aside>

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

      <section className="mt-10">
        <a
          href="/research/codec"
          className="block rounded-lg border border-zinc-200 dark:border-zinc-800 bg-gradient-to-br from-blue-50 to-zinc-50 dark:from-blue-950/30 dark:to-zinc-900 p-5 hover:border-blue-400 dark:hover:border-blue-600 transition"
        >
          <div className="flex items-baseline justify-between gap-3 mb-1">
            <div className="font-semibold">Track B: building the codec</div>
            <span className="text-[10px] uppercase tracking-wider text-blue-600 dark:text-blue-400 font-semibold">
              New
            </span>
          </div>
          <div className="text-sm text-zinc-600 dark:text-zinc-400">
            Five rounds of optimization on top of the v4 vocabulary: symbol
            repetition, multi-band parallel symbols, Hamming(7,4) forward
            error correction, and pilot-tone calibration. With charts.
          </div>
        </a>
      </section>
    </article>
  );
}
