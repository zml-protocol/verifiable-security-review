# Pinned, project-local Go toolchain for ground-truth probes (source this file).
# Installed from go.dev/dl, sha256-verified:
#   go1.26.8.linux-amd64.tar.gz d0f743b33e8d8945e6b1f432edd15785c70507121d6e2a723b21285eddf8b57b
_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export GOROOT="$_root/.cache/toolchains/go1.26.8"
export PATH="$GOROOT/bin:$PATH"
export GOPATH="$_root/.cache/go"
export GOMODCACHE="$_root/.cache/go/pkg/mod"
export GOCACHE="$_root/.cache/go-build"
export GOTOOLCHAIN=local   # never auto-download a different toolchain
export GOFLAGS=-mod=readonly   # build exactly the dependency versions pinned by go.mod/go.sum
export CGO_ENABLED=0
