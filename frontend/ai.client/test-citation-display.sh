#!/bin/bash
# Simple test script to verify citation display component tests

echo "Running citation display component tests..."
cd "$(dirname "$0")"

# Try to run the specific test file
npm test -- --include='**/citation-display.component.spec.ts' --watch=false --browsers=ChromeHeadless 2>&1 | tee test-output.log

# Check if tests passed
if grep -q "TOTAL.*100%" test-output.log; then
  echo "✓ All tests passed!"
  exit 0
else
  echo "✗ Some tests failed or could not run"
  exit 1
fi
