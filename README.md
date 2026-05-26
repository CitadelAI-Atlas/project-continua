# Project Continua

Math-native acoustic communication. Audio designed so that the math IS the
meaning, not a label sitting on top of it.

**Live site:** [project-continua.vercel.app](https://project-continua.vercel.app)

## What it is

Project Continua is building a small vocabulary of audio primitives whose
meaning is the sound's mathematical structure itself: integer frequency
ratios, periodic timing, continuous transformation, discrete state
sequences, co-presence, ordered sequence, ostensive demonstration. The
primitives compose into higher-level statements the way notes compose into
chords or words into sentences.

The work runs along two complementary tracks:

- **Track A: teach humans this language.** Use math-native audio as a
  medium humans can learn to perceive, internalize, and use fluently.
  The current v4 dashboard at `/dashboards/v4` is a Learn / Test / History
  flow for the seven cross-model-stable primitives, with speech-to-text
  input for free-response answers.
- **Track B: build it as an efficient codec.** Math-native encoding as a
  high-density, low-overhead channel for transmitting rich data via audio.
  See `/research/codec` on the live site for the five-round optimization
  pass and the bake-off across white, pink, and reverberant noise.

A third research thread (`/research/bandwidth`) measures the raw
acoustic-channel ceiling via a textbook OFDM design (BPSK / QPSK / 16-QAM
across 64 subcarriers), so the math-native trade-off can be quantified
against a fair upper bound.

The AI-receiver experiment at `/research/decode-experiment` sends math
expressions through both encoding paths and asks an AI receiver, given
the v4 vocabulary, to decode the audio.

## Repository layout

```
project-continua/
├── continua/          # Python: encoder, analyzer, vocabulary, codec, OFDM
├── data/wavs/         # Rendered audio examples (committed; part of the research)
├── scripts/           # Render, benchmark, and bake-off scripts
├── tests/             # Benchmark suites
└── web/               # Public website (Next.js + MDX + Tailwind v4)
```

## Running the site locally

```bash
cd web
npm install
npm run dev    # http://localhost:3000
```

## Running benchmarks locally

```bash
pip3 install -r requirements.txt
python3 scripts/codec_benchmark.py --trials 10
python3 scripts/ofdm_benchmark.py --trials 16
python3 scripts/codec_bakeoff.py --trials 12
```

Each benchmark writes per-cell JSON results to a local gitignored
output directory. The public site embeds chart images rendered from
those results by `scripts/codec_bakeoff_charts.py`.

## A note on this repository

The public artifacts are the website plus the code in this repo. The
working copy on the author's machine also carries some local-only
files (session notes, draft documents, raw per-iteration data) that
are intentionally kept out of version control. All results published
on the live site are reproducible from the code that is here.

## Lineage

Pythagorean music-as-math; Hans Freudenthal's *Lincos* (1960); SETI / METI;
contemporary research on receiver-derivable mathematical encodings; the
stenotype machine, where a court reporter's chord-keying inspired the
project's framing of simultaneity as bandwidth.

## License

[MIT](LICENSE) for the code. Audio examples are CC-BY (preliminary).
