// Minimal Caddy build for the truth probe, copied unchanged to cmd/truthprobe/
// at both the base and the head commit. Upstream's standard build does not
// compile in this commit window (go.mod pins otel/sdk v1.21.0 with otel/trace
// v1.29.0, fixed later by caddyserver/caddy#6676), so, as xcaddy does, only
// the modules this probe needs are registered. The code under test and every
// pinned dependency version are left untouched.
package main

import (
	caddycmd "github.com/caddyserver/caddy/v2/cmd"

	_ "github.com/caddyserver/caddy/v2/caddyconfig/caddyfile"
	_ "github.com/caddyserver/caddy/v2/caddyconfig/httpcaddyfile"
	_ "github.com/caddyserver/caddy/v2/modules/caddyhttp"
	_ "github.com/caddyserver/caddy/v2/modules/caddyhttp/headers"
	_ "github.com/caddyserver/caddy/v2/modules/caddyhttp/reverseproxy"
	_ "github.com/caddyserver/caddy/v2/modules/caddyhttp/reverseproxy/forwardauth"
)

func main() {
	caddycmd.Main()
}
