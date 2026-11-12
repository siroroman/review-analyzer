#!/usr/bin/env bash
# Per-file and critical-module coverage thresholds (docs/agents/testing.md, Coverage).
# Usage: coverage json -o - | check-coverage.sh      (reads the coverage.py JSON report on stdin)
# Fails when a file is below 80 % or a critical module (metrics, sanitize, budget, llm) is below 95 %.
# Percentage = (covered lines + covered branches) / (statements + branches), as pytest-cov reports it.
# The overall 90 % is `--cov-fail-under=90` in pytest and diff coverage is diff-cover; this covers what they do not.
set -euo pipefail

FILE_MIN=80
CRITICAL_MIN=95
CRITICAL='metrics sanitize budget llm'

jq -e --argjson fmin "$FILE_MIN" --argjson cmin "$CRITICAL_MIN" --arg crit "$CRITICAL" '
  def pct(c; t): if t == 0 then 100 else (c * 100 / t) end;
  def sums: {c: (map(.summary.covered_lines + .summary.covered_branches) | add // 0),
             t: (map(.summary.num_statements + .summary.num_branches) | add // 0)};
  (.files | to_entries) as $all
  | if ($all | length) == 0 then error("empty coverage report") else . end
  | [ $all[] | select((.value.summary.num_statements + .value.summary.num_branches) > 0)
      | {name: .key, p: pct(.value.summary.covered_lines + .value.summary.covered_branches;
                            .value.summary.num_statements + .value.summary.num_branches)}
      | select(.p < $fmin) | "file below \($fmin) %: \(.name) (\(.p * 10 | round / 10) %)" ] as $files
  | [ ($crit | split(" "))[] as $m
      | ($all | map(select(.key | test("(^|/)app/" + $m + "/"))) | map(.value)) as $v
      | ($v | sums) as $s
      | select($s.t > 0 and pct($s.c; $s.t) < $cmin)
      | "critical module below \($cmin) %: \($m) (\(pct($s.c; $s.t) * 10 | round / 10) %)" ] as $mods
  | ($files + $mods) as $errors
  | if ($errors | length) > 0 then ($errors | join("\n") | halt_error(1)) else "coverage thresholds met" end
' -r
