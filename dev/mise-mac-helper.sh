#!/usr/bin/bash
set -eu

if [[ "$(uname -s)" != "Darwin" ]]; then
    exit 0
fi

# DEBT(bhee): old version of cryptography, requiring an old version of openssl.
# Assumes the user has run:
# brew install -f openssl@1.1
export CPPFLAGS="${CPPFLAGS:-} -I/opt/homebrew/opt/openssl@1.1/include"
export LDFLAGS="${LDFLAGS:-} -L/opt/homebrew/opt/openssl@1.1/lib"

# Assumes the user has run:
# brew install libpq
export PATH="$PATH:/opt/homebrew/opt/libpq/bin"
