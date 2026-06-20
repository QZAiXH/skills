#!/usr/bin/env bash
# Human-in-the-loop reproduction loop for cs-diagnose
# Copy this file to your issue directory, edit the steps below, and run it.
#
# Usage:
#   bash {slug}-feedback-loop.sh
#
# Two helpers:
#   step "<instruction>"          → show instruction, wait for Enter
#   capture VAR "<question>"      → show question, read response into VAR
#
# At the end, captured values are printed as KEY=VALUE for the agent to parse.

set -euo pipefail

step() {
  printf '\n>>> %s\n' "$1"
  read -r -p "    [Enter when done] " _
}

capture() {
  local var="$1" question="$2" answer
  printf '\n>>> %s\n' "$question"
  read -r -p "    > " answer
  printf -v "$var" '%s' "$answer"
}

# --- edit below ---------------------------------------------------------
# Replace these with actual reproduction steps for your bug

step "Open the app at http://localhost:3000 and sign in."

step "Navigate to the [specific page/feature]."

capture ACTION_RESULT "Perform [specific action]. Did it succeed? (y/n)"

capture ERROR_MSG "If failed, paste the error message (or 'none'):"

capture ADDITIONAL_INFO "Any additional observations:"

# --- edit above ---------------------------------------------------------

printf '\n--- Captured ---\n'
printf 'ACTION_RESULT=%s\n' "$ACTION_RESULT"
printf 'ERROR_MSG=%s\n' "$ERROR_MSG"
printf 'ADDITIONAL_INFO=%s\n' "$ADDITIONAL_INFO"
