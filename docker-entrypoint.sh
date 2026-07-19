#!/bin/sh
set -e

# Check if we should just run migrations
if [ "$1" = "migrate" ]; then
    echo "Running migrations..."
    cd /AuthService/app
    exec uv run alembic upgrade head
fi

echo "Waiting for Redis to be ready..."
while ! nc -z redis 6379; do
  sleep 1
done
echo "Redis is ready!"

export PYTHONPATH="/AuthService:/AuthService/app:$PYTHONPATH"

RUN_TESTS=${RUN_TESTS:-"false"}
TEST_TYPE=${TEST_TYPE:-"all"}

if [ "$RUN_TESTS" = "true" ]; then
    echo "Running tests..."
    cd /AuthService/app

    # Initialize counters
    TOTAL_TESTS=0
    TOTAL_PASSED=0
    TOTAL_FAILED=0
    TOTAL_XFAILED=0
    TOTAL_ERRORS=0

    # Function to parse pytest output and extract results
    parse_test_results() {
        local output="$1"

        local passed=$(echo "$output" | grep -oE '[0-9]+ passed' | tail -1 | grep -oE '[0-9]+')
        local failed=$(echo "$output" | grep -oE '[0-9]+ failed' | tail -1 | grep -oE '[0-9]+')
        local xfailed=$(echo "$output" | grep -oE '[0-9]+ xfailed' | tail -1 | grep -oE '[0-9]+')
        local errors=$(echo "$output" | grep -oE '[0-9]+ errors' | tail -1 | grep -oE '[0-9]+')

        passed=${passed:-0}
        failed=${failed:-0}
        xfailed=${xfailed:-0}
        errors=${errors:-0}

        TOTAL_PASSED=$((TOTAL_PASSED + passed))
        TOTAL_FAILED=$((TOTAL_FAILED + failed))
        TOTAL_XFAILED=$((TOTAL_XFAILED + xfailed))
        TOTAL_ERRORS=$((TOTAL_ERRORS + errors))

        local group_total=$((passed + failed + xfailed + errors))
        TOTAL_TESTS=$((TOTAL_TESTS + group_total))
    }

    # Run pytest with real-time output (no capture)
    run_pytest() {
        local test_path="$1"
        local test_name="$2"

        echo ""
        echo "=== $test_name ==="

        # Run pytest directly without capturing output
        uv run pytest "$test_path" -v --tb=short --color=yes

        # Capture the exit code
        local exit_code=$?

        # Run again with capture to parse results
        local output=$(uv run pytest "$test_path" -v --tb=short 2>&1 || true)
        parse_test_results "$output"

        return $exit_code
    }

    case "$TEST_TYPE" in
        "unit")
            run_pytest "../tests/unit/" "UNIT TESTS"
            ;;
        "integration")
            run_pytest "../tests/integration/" "INTEGRATION TESTS"
            ;;
        "security")
            run_pytest "../tests/security-abuse/" "COMPONENT TESTS"
            ;;
        "concurrency")
            run_pytest "../tests/concurrency/" "End to End TESTS"
            ;;
        "all")
            run_pytest "../tests/unit/" "UNIT TESTS"
            run_pytest "../tests/integration/" "INTEGRATION TESTS"
            run_pytest "../tests/component/" "COMPONENT TESTS"
            run_pytest "../tests/end-to-end/" "End-to-End TESTS"
            ;;
        *)
            echo "Unknown TEST_TYPE: $TEST_TYPE"
            exit 1
            ;;
    esac

    # Display final summary
    echo ""
    echo "========================================"
    echo "          TEST SUMMARY"
    echo "========================================"
    echo "Total Tests:  $TOTAL_TESTS"
    echo "Passed:       $TOTAL_PASSED"
    echo "Failed:       $TOTAL_FAILED"
    echo "XFailed:      $TOTAL_XFAILED"
    echo "Errors:       $TOTAL_ERRORS"
    echo "----------------------------------------"
    if [ $TOTAL_FAILED -eq 0 ] && [ $TOTAL_ERRORS -eq 0 ]; then
        echo "✅ ALL TESTS PASSED!"
    else
        echo "❌ Some tests failed!"
    fi
    echo "========================================"
    echo ""

    echo "Tests completed. Continuing with application startup..."
else
    echo "Tests skipped (RUN_TESTS=false)"
fi

cd /AuthService/app
echo "Starting application..."
exec uv run uvicorn app.main:app --port 8000 --host 0.0.0.0