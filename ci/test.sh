#!/usr/bin/env bash
set -uo pipefail

EXIT=0

for pymodule in python-modules/cis_*; do
    printf "Tests for %s\n\n" "$pymodule"
    cd "$pymodule" && pytest
    CURRENT=$?
    if [[ $CURRENT -eq 5 || $CURRENT -eq 0 ]]; then
        cd - || exit 1
    fi
    EXIT=$CURRENT
done

exit $EXIT
