"""continua v4 - receiver-derivable, math-native acoustic language.

Defining constraint: derivability without shared spec. A receiver with
knowledge of mathematics + acoustic physics, but no prior knowledge of
the continua vocabulary, must be able to infer the meaning of a message
from its observable mathematical structure alone.

v2 and v3 quietly violated this: they relied on a shared agreement that
"this audio means SELF, that audio means TARGET." v4 includes only
primitives whose meaning the math itself carries.

Excluded (relocated to affect channel or out of scope):
  SELF, TARGET   - deixis is convention, no math operation carries it
  ALL, SOME      - quantification needs set-theory context
  NOT (logical)  - convention; operational NEGATE survives because its
                   cancellation behavior IS observable in combination

Included:
  COUNT(N), RATIO(p:q), EQUAL, GREATER, LESSER, BECOMES, AND, OR,
  PERIOD(T, x), NEGATE(x)

See docs/vocabulary_v4_spec.md.
"""
