#!/usr/bin/env bash
# Shared helpers of the PR body checks. Sourced, never run. Not a check, so it has no test of its own:
# the tests of the checks that use it cover it.

# pr_section <body-file> <heading>: the text under `## <heading>` up to the next `## `, without HTML comments
# (the template's hints) and blank lines. CRLF line endings are accepted.
pr_section() {
  tr -d '\r' < "$1" \
    | perl -0pe 's/<!--.*?-->//gs' \
    | awk -v h="## $2" '
        /^## / { inside = ($0 == h); next }
        inside && NF { print }'
}

# pr_section_declares <body-file> <heading>: succeeds when the section has text other than "none".
pr_section_declares() {
  local text
  text=$(pr_section "$1" "$2" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:].')
  [[ -n "$text" && "$text" != none ]]
}

# pr_body_has_warning <body-file>: the PR body starts with `> **Warning:**` and a reason.
pr_body_has_warning() {
  local first
  first=$(tr -d '\r' < "$1" | awk 'NF { print; exit }')
  [[ "$first" =~ ^'> **Warning:**'[[:space:]]*[^[:space:]] ]]
}
