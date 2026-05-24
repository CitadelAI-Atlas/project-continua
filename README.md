# Project Continua

Math-native acoustic communication. Audio designed so that the math IS the
meaning, not a label on top of it.

**Live site:** [projectcontinua.ai](https://projectcontinua.ai) (in progress at [project-continua.vercel.app](https://project-continua.vercel.app))

## What it is

Project Continua is building a small vocabulary of audio primitives whose
meaning is grounded in shared math and physics: integer frequency ratios,
periodic timing, continuous transformation, co-presence, ordered sequence.
The primitives compose into higher-level statements the way notes compose
into chords or words into sentences.

The work runs along two complementary tracks:

- **Track A: teach humans this language.** Use math-native audio as a
  medium humans can learn to perceive, internalize, and use fluently.
- **Track B: build it as an efficient codec.** Math-native encoding as a
  high-density, low-overhead channel for transmitting rich data via audio.

## Running locally

Requires Python 3.9+, numpy, scipy, and Flask.

```bash
pip3 install -r requirements.txt
python3 app.py  # http://localhost:5173
```

## Layout

```
project-continua/
├── continua/          # Python package (encoder, analyzer, vocabulary)
├── data/wavs/         # Rendered audio examples
├── scripts/           # Render and utility scripts
├── tests/             # Benchmark suites
├── web/               # Public website (Next.js + MDX)
├── static/            # Browser dashboard for the learn-and-test flow
└── app.py             # Flask server for the dashboard
```

## Lineage

Pythagorean music-as-math; Hans Freudenthal's *Lincos* (1960); SETI / METI;
contemporary research on receiver-derivable mathematical encodings.

## License

Code license TBD. Audio examples CC-BY (preliminary).
