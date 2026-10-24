# Design and acceptance contract

User: a support/performance engineer sharing evidence of slow or failing requests.
Flow: capture locally → derive a performance-only report → inspect it → share the
derived report. Captures are never fetched, replayed, uploaded or rewritten.

Acceptance: all uncontrolled captured text must be absent from both outputs;
relative timing and known numeric examples must remain correct; unknown values
must remain distinct from zero; invalid inputs cannot create a report; existing
output and source files cannot be replaced; a fresh wheel installation must run
the documented example outside the checkout.

Core objects are newly constructed with fixed keys. Methods and MIME types map
to a closed vocabulary. No source object, URL, extension field or absolute date
is passed to the renderer. Timestamp parsing requires explicit timezones; all
times are rounded to 0.001 ms. Percentiles use nearest rank. Decoded body size is
labeled separately from transfer size. HAR ssl time overlaps connect time.

Visual design: a quiet blue/white technical report, system sans-serif typography,
one shared duration scale and status colors with equivalent text labels. Native
details controls expose phases; a keyboard-focusable horizontal table preserves
readability on small screens. No animation, script, external font or asset.

This is not a HAR redaction engine or formal anonymization. Numeric fingerprints
are retained on purpose. Tests mutate discarded fields and assert output
invariance, plant synthetic private markers, and exercise malformed JSON/numbers.
