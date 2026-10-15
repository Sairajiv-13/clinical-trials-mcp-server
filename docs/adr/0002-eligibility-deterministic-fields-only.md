# ADR 0002: Eligibility checks cover age and sex only

Status: Accepted
Date: 2026-10-14

## Context

`eligibility_check` is the tool most likely to be misread as a clinical
decision. A study record has exactly three structured eligibility fields:
`sex`, `minimumAge`, and `maximumAge`. Everything else (diagnosis details,
lab thresholds, prior treatment, washout periods) is free text written for
clinicians, in `eligibilityCriteria`. Any verdict this tool returns has to
be honest about that split.

## Decision

The tool evaluates age range and sex exactly, returns a verdict of
`meets`, `does_not_meet`, or `cannot_determine`, and attaches the full
free-text criteria to every result for a person to review.

- A single failed check makes the verdict `does_not_meet`. A check that
  cannot be run (no patient age given, a bound the study does not state)
  makes it `cannot_determine`, never a silent pass.
- Age strings from the API ("18 Years", "6 Months") are parsed into years
  for comparison; the original string is what appears in the explanation.
- The result carries a fixed note stating that only age and sex were
  checked and that the verdict is not a final eligibility decision.

## Alternatives considered

Parse the free-text criteria with rules for common patterns (HbA1c ranges,
prior therapy, lab values). Rejected: the patterns vary too much between
sponsors, a wrong extraction looks identical to a right one, and the
failure mode is telling a coordinator a patient fits when they do not.

Send the criteria to an LLM and return its judgment. Rejected for the same
reason, plus cost and non-determinism: the same patient and study could
get different verdicts on different days, and nothing in the result would
show why.

Return the structured fields with no verdict at all. Safe, but it pushes
trivial comparisons (is 45 between 18 and 75) onto the caller for no
benefit. The verdict is worth having as long as its scope is stated.

## Consequences

- `meets` means "passes the age and sex fields", and the output says so
  every time. Callers that show the verdict to users should show the note
  with it.
- Studies that omit age bounds or enroll all sexes produce shorter check
  lists, and a patient with no age provided gets `cannot_determine`, by
  design.
- If the API ever adds more structured criteria, this ADR is the place to
  revisit; the check functions in `eligibility.py` are one per field, so
  adding a field is a contained change.
