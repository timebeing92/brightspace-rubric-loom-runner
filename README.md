# Rubric Loom

This repository is the user-facing local runner for Rubric Loom. It will pair
one guided terminal application with one exact
[`brightspace-rubric-bundle`](https://github.com/timebeing92/brightspace-rubric-bundle)
release so colleagues can download a ZIP, unpack it, and start without cloning
multiple repositories or navigating the producer's engineering surface.

Rubric Loom has two doors:

- **Unravel** reads Brightspace course-export ZIPs, unpacked exports, or bare
  `rubrics_d2l.xml` files and produces review workbooks, JSON, and DOCX.
- **Weave** reads supported DOCX, Markdown, or JSON rubric sources and produces
  a validated rubric-only Brightspace import package after explicit review.

The runner owns launchers, setup, updates, persistent user data, and the
one-download release experience. Rubric extraction, normalization, scoring,
XML construction, package validation, and progress contracts remain in the
bundle.

Status: initial runner implementation in progress. No public runner release has
been cut yet.
