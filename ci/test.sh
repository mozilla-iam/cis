#!/usr/bin/env bash
set -uo pipefail

EXIT=0

for pymodule in python-modules/cis_*; do
    printf "Tests for %s\n\n" "$pymodule"
    cd "$pymodule" && pytest
    CURRENT=$?
    if [[ $CURRENT -ne 0 ]]; then
        EXIT=$CURRENT
    fi
    cd - || exit 1
done

exit $EXIT
