# Hop review sheet

For each item decide whether the stated link holds in the code shown, under the relation's definition: TRUE, FALSE, or INDETERMINATE (the code shown and the repository do not settle it). Judge each item on its own.

## R001

- code: caddy, revision `head`
- relation `field_flow`: Value flowing through locals into a struct field. `from` defines a local variable; `to` is a keyed struct literal field f: e or a field store x.f = e; the value defined at `from` reaches e within the function (through local variables, and calls that derive their result from it).
- **from** (definition): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 211-217, starting at `handler := &headers.Handler{`

```
     205 | 	// values aren't empty, because the header handler would not replace
     206 | 	// placeholders which have no value.
     207 | 	copyHeaderRoutes := []caddyhttp.Route{}
     208 | 	for _, from := range sortedHeadersToCopy {
     209 | 		to := http.CanonicalHeaderKey(headersToCopy[from])
     210 | 		placeholderName := "http.reverse_proxy.header." + http.CanonicalHeaderKey(from)
>>   211 | 		handler := &headers.Handler{
>>   212 | 			Request: &headers.HeaderOps{
>>   213 | 				Set: http.Header{
>>   214 | 					to: []string{"{" + placeholderName + "}"},
>>   215 | 				},
>>   216 | 			},
>>   217 | 		}
     218 | 		copyHeaderRoutes = append(copyHeaderRoutes, caddyhttp.Route{
     219 | 			MatcherSetsRaw: []caddy.ModuleMap{{
     220 | 				"not": h.JSON(caddyhttp.MatchNot{MatcherSetsRaw: []caddy.ModuleMap{{
     221 | 					"vars": h.JSON(caddyhttp.VarsMatcher{"{" + placeholderName + "}": []string{""}}),
     222 | 				}}}),
     223 | 			}},
```

- **to** (keyed_field, field_store): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 224-229, starting at `HandlersRaw: []json.RawMessage{caddyconfig.JSONModuleObject( handler, "handler", "headers", nil, )},`

```
     218 | 		copyHeaderRoutes = append(copyHeaderRoutes, caddyhttp.Route{
     219 | 			MatcherSetsRaw: []caddy.ModuleMap{{
     220 | 				"not": h.JSON(caddyhttp.MatchNot{MatcherSetsRaw: []caddy.ModuleMap{{
     221 | 					"vars": h.JSON(caddyhttp.VarsMatcher{"{" + placeholderName + "}": []string{""}}),
     222 | 				}}}),
     223 | 			}},
>>   224 | 			HandlersRaw: []json.RawMessage{caddyconfig.JSONModuleObject(
>>   225 | 				handler,
>>   226 | 				"handler",
>>   227 | 				"headers",
>>   228 | 				nil,
>>   229 | 			)},
     230 | 		})
     231 | 	}
     232 | 
     233 | 	goodResponseHandler.Routes = append(goodResponseHandler.Routes, copyHeaderRoutes...)
     234 | 
     235 | 	// note that when a response has any other status than 2xx, then we
```

## R002

- code: caddy, revision `base`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `modules/caddyhttp/reverseproxy/reverseproxy.go` lines 958-958, starting at `routeErr := rh.Routes.Compile(next).ServeHTTP(rw, origReq.WithContext(ctx))`

```
     952 | 			logger:   logger,
     953 | 		}
     954 | 		ctx := origReq.Context()
     955 | 		ctx = context.WithValue(ctx, proxyHandleResponseContextCtxKey, hrc)
     956 | 
     957 | 		// pass the request through the response handler routes
>>   958 | 		routeErr := rh.Routes.Compile(next).ServeHTTP(rw, origReq.WithContext(ctx))
     959 | 
     960 | 		// close the response body afterwards, since we don't need it anymore;
     961 | 		// either a route had 'copy_response' which already consumed the body,
     962 | 		// or some other terminal handler ran which doesn't need the response
     963 | 		// body after that point (e.g. 'file_server' for X-Accel-Redirect flow),
     964 | 		// or we fell through to subsequent handlers past this proxy
```

- **to** (any): `modules/caddyhttp/headers/headers.go` lines 94-94, starting at `h.Request.ApplyToRequest(r)`

```
      88 | }
      89 | 
      90 | func (h Handler) ServeHTTP(w http.ResponseWriter, r *http.Request, next caddyhttp.Handler) error {
      91 | 	repl := r.Context().Value(caddy.ReplacerCtxKey).(*caddy.Replacer)
      92 | 
      93 | 	if h.Request != nil {
>>    94 | 		h.Request.ApplyToRequest(r)
      95 | 	}
      96 | 
      97 | 	if h.Response != nil {
      98 | 		if h.Response.Deferred || h.Response.Require != nil {
      99 | 			w = &responseWriterWrapper{
     100 | 				ResponseWriterWrapper: &caddyhttp.ResponseWriterWrapper{ResponseWriter: w},
```

## R003

- code: caddy, revision `base`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 215-215, starting at `rpHandler.HandleResponse = append(rpHandler.HandleResponse, goodResponseHandler)`

```
     209 | 
     210 | 	// note that when a response has any other status than 2xx, then we
     211 | 	// use the reverse proxy's default behaviour of copying the response
     212 | 	// back to the client, so we don't need to explicitly add a response
     213 | 	// handler specifically for that behaviour; we do need the 2xx handler
     214 | 	// though, to make handling fall through to handlers deeper in the chain.
>>   215 | 	rpHandler.HandleResponse = append(rpHandler.HandleResponse, goodResponseHandler)
     216 | 
     217 | 	// the rest of the config is specified by the user
     218 | 	// using the reverse_proxy directive syntax
     219 | 	dispenser.Next() // consume the directive name
     220 | 	err = rpHandler.UnmarshalCaddyfile(dispenser)
     221 | 	if err != nil {
```

- **to** (any): `modules/caddyhttp/headers/headers.go` lines 93-95, starting at `if h.Request != nil {`

```
      87 | 	return nil
      88 | }
      89 | 
      90 | func (h Handler) ServeHTTP(w http.ResponseWriter, r *http.Request, next caddyhttp.Handler) error {
      91 | 	repl := r.Context().Value(caddy.ReplacerCtxKey).(*caddy.Replacer)
      92 | 
>>    93 | 	if h.Request != nil {
>>    94 | 		h.Request.ApplyToRequest(r)
>>    95 | 	}
      96 | 
      97 | 	if h.Response != nil {
      98 | 		if h.Response.Deferred || h.Response.Require != nil {
      99 | 			w = &responseWriterWrapper{
     100 | 				ResponseWriterWrapper: &caddyhttp.ResponseWriterWrapper{ResponseWriter: w},
     101 | 				replacer:              repl,
```

## R004

- code: caddy, revision `base`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 111-111, starting at `headersToCopy := make(map[string]string)`

```
     105 | 		HandleResponse: []caddyhttp.ResponseHandler{},
     106 | 	}
     107 | 
     108 | 	// collect the headers to copy from the auth response
     109 | 	// onto the original request, so they can get passed
     110 | 	// through to a backend app
>>   111 | 	headersToCopy := make(map[string]string)
     112 | 
     113 | 	// read the subdirectives for configuring the forward_auth shortcut
     114 | 	// NOTE: we delete the tokens as we go so that the reverse_proxy
     115 | 	// unmarshal doesn't see these subdirectives which it cannot handle
     116 | 	for dispenser.Next() {
     117 | 		for dispenser.NextBlock(0) {
```

- **to** (any): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 195-195, starting at `handler.Request.Set.Set(to, "{http.reverse_proxy.header."+http.CanonicalHeaderKey(from)+"}")`

```
     189 | 	}
     190 | 
     191 | 	// the list of headers to copy may be empty, but that's okay; we
     192 | 	// need at least one handler in the routes for the response handling
     193 | 	// logic in reverse_proxy to not skip this entry as empty.
     194 | 	for from, to := range headersToCopy {
>>   195 | 		handler.Request.Set.Set(to, "{http.reverse_proxy.header."+http.CanonicalHeaderKey(from)+"}")
     196 | 	}
     197 | 
     198 | 	goodResponseHandler.Routes = append(
     199 | 		goodResponseHandler.Routes,
     200 | 		caddyhttp.Route{
     201 | 			HandlersRaw: []json.RawMessage{caddyconfig.JSONModuleObject(
```

## R005

- code: caddy, revision `head`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 219-223, starting at `MatcherSetsRaw: []caddy.ModuleMap{{ "not": h.JSON(caddyhttp.MatchNot{MatcherSetsRaw: []caddy.ModuleMap{{ "vars": h.JSON(caddyhttp.VarsMatcher{"{" + placeholderName + "}": []string{""}}),`

```
     213 | 				Set: http.Header{
     214 | 					to: []string{"{" + placeholderName + "}"},
     215 | 				},
     216 | 			},
     217 | 		}
     218 | 		copyHeaderRoutes = append(copyHeaderRoutes, caddyhttp.Route{
>>   219 | 			MatcherSetsRaw: []caddy.ModuleMap{{
>>   220 | 				"not": h.JSON(caddyhttp.MatchNot{MatcherSetsRaw: []caddy.ModuleMap{{
>>   221 | 					"vars": h.JSON(caddyhttp.VarsMatcher{"{" + placeholderName + "}": []string{""}}),
>>   222 | 				}}}),
>>   223 | 			}},
     224 | 			HandlersRaw: []json.RawMessage{caddyconfig.JSONModuleObject(
     225 | 				handler,
     226 | 				"handler",
     227 | 				"headers",
     228 | 				nil,
     229 | 			)},
```

- **to** (any): `modules/caddyhttp/headers/headers.go` lines 93-95, starting at `if h.Request != nil {`

```
      87 | 	return nil
      88 | }
      89 | 
      90 | func (h Handler) ServeHTTP(w http.ResponseWriter, r *http.Request, next caddyhttp.Handler) error {
      91 | 	repl := r.Context().Value(caddy.ReplacerCtxKey).(*caddy.Replacer)
      92 | 
>>    93 | 	if h.Request != nil {
>>    94 | 		h.Request.ApplyToRequest(r)
>>    95 | 	}
      96 | 
      97 | 	if h.Response != nil {
      98 | 		if h.Response.Deferred || h.Response.Require != nil {
      99 | 			w = &responseWriterWrapper{
     100 | 				ResponseWriterWrapper: &caddyhttp.ResponseWriterWrapper{ResponseWriter: w},
     101 | 				replacer:              repl,
```

## R006

- code: caddy, revision `head`
- relation `guard_property`: Condition that is a property of an object on the path, not on the flow. `from` is a keyed struct literal field anywhere inside the literal (through literal elements, keyed values and &) that initializes a local variable v; `to` is a field store v.f = e that reads that same definition of v.
- **from** (keyed_field): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 218-219, starting at `MatcherSetsRaw: []caddy.ModuleMap{{`

```
     212 | 			Request: &headers.HeaderOps{
     213 | 				Set: http.Header{
     214 | 					to: []string{"{" + placeholderName + "}"},
     215 | 				},
     216 | 			},
     217 | 		}
>>   218 | 		copyHeaderRoutes = append(copyHeaderRoutes, caddyhttp.Route{
>>   219 | 			MatcherSetsRaw: []caddy.ModuleMap{{
     220 | 				"not": h.JSON(caddyhttp.MatchNot{MatcherSetsRaw: []caddy.ModuleMap{{
     221 | 					"vars": h.JSON(caddyhttp.VarsMatcher{"{" + placeholderName + "}": []string{""}}),
     222 | 				}}}),
     223 | 			}},
     224 | 			HandlersRaw: []json.RawMessage{caddyconfig.JSONModuleObject(
     225 | 				handler,
```

- **to** (field_store): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 233-233, starting at `goodResponseHandler.Routes = append(goodResponseHandler.Routes, copyHeaderRoutes...)`

```
     227 | 				"headers",
     228 | 				nil,
     229 | 			)},
     230 | 		})
     231 | 	}
     232 | 
>>   233 | 	goodResponseHandler.Routes = append(goodResponseHandler.Routes, copyHeaderRoutes...)
     234 | 
     235 | 	// note that when a response has any other status than 2xx, then we
     236 | 	// use the reverse proxy's default behaviour of copying the response
     237 | 	// back to the client, so we don't need to explicitly add a response
     238 | 	// handler specifically for that behaviour; we do need the 2xx handler
     239 | 	// though, to make handling fall through to handlers deeper in the chain.
```

## R007

- code: caddy, revision `head`
- relation `guard_property`: Condition that is a property of an object on the path, not on the flow. `from` is a keyed struct literal field anywhere inside the literal (through literal elements, keyed values and &) that initializes a local variable v; `to` is a field store v.f = e that reads that same definition of v.
- **from** (keyed_field): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 181-183, starting at `Match: &caddyhttp.ResponseMatcher{`

```
     175 | 	// then we will copy some headers from the response onto the original
     176 | 	// request, and allow handling to continue down the middleware chain,
     177 | 	// by _not_ executing a terminal handler. We must have at least one
     178 | 	// route in the response handler, even if it's no-op, so that the
     179 | 	// response handling logic in reverse_proxy doesn't skip this entry.
     180 | 	goodResponseHandler := caddyhttp.ResponseHandler{
>>   181 | 		Match: &caddyhttp.ResponseMatcher{
>>   182 | 			StatusCode: []int{2},
>>   183 | 		},
     184 | 		Routes: []caddyhttp.Route{
     185 | 			{
     186 | 				HandlersRaw: []json.RawMessage{caddyconfig.JSONModuleObject(
     187 | 					&caddyhttp.VarsMiddleware{},
     188 | 					"handler",
     189 | 					"vars",
```

- **to** (field_store): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 233-233, starting at `goodResponseHandler.Routes = append(goodResponseHandler.Routes, copyHeaderRoutes...)`

```
     227 | 				"headers",
     228 | 				nil,
     229 | 			)},
     230 | 		})
     231 | 	}
     232 | 
>>   233 | 	goodResponseHandler.Routes = append(goodResponseHandler.Routes, copyHeaderRoutes...)
     234 | 
     235 | 	// note that when a response has any other status than 2xx, then we
     236 | 	// use the reverse proxy's default behaviour of copying the response
     237 | 	// back to the client, so we don't need to explicitly add a response
     238 | 	// handler specifically for that behaviour; we do need the 2xx handler
     239 | 	// though, to make handling fall through to handlers deeper in the chain.
```

## R008

- code: caddy, revision `base`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 215-215, starting at `rpHandler.HandleResponse = append(rpHandler.HandleResponse, goodResponseHandler)`

```
     209 | 
     210 | 	// note that when a response has any other status than 2xx, then we
     211 | 	// use the reverse proxy's default behaviour of copying the response
     212 | 	// back to the client, so we don't need to explicitly add a response
     213 | 	// handler specifically for that behaviour; we do need the 2xx handler
     214 | 	// though, to make handling fall through to handlers deeper in the chain.
>>   215 | 	rpHandler.HandleResponse = append(rpHandler.HandleResponse, goodResponseHandler)
     216 | 
     217 | 	// the rest of the config is specified by the user
     218 | 	// using the reverse_proxy directive syntax
     219 | 	dispenser.Next() // consume the directive name
     220 | 	err = rpHandler.UnmarshalCaddyfile(dispenser)
     221 | 	if err != nil {
```

- **to** (any): `modules/caddyhttp/reverseproxy/reverseproxy.go` lines 958-958, starting at `routeErr := rh.Routes.Compile(next).ServeHTTP(rw, origReq.WithContext(ctx))`

```
     952 | 			logger:   logger,
     953 | 		}
     954 | 		ctx := origReq.Context()
     955 | 		ctx = context.WithValue(ctx, proxyHandleResponseContextCtxKey, hrc)
     956 | 
     957 | 		// pass the request through the response handler routes
>>   958 | 		routeErr := rh.Routes.Compile(next).ServeHTTP(rw, origReq.WithContext(ctx))
     959 | 
     960 | 		// close the response body afterwards, since we don't need it anymore;
     961 | 		// either a route had 'copy_response' which already consumed the body,
     962 | 		// or some other terminal handler ran which doesn't need the response
     963 | 		// body after that point (e.g. 'file_server' for X-Accel-Redirect flow),
     964 | 		// or we fell through to subsequent handlers past this proxy
```

## R009

- code: filebrowser, revision `base`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `http/raw.go` lines 129-135, starting at `archiveFiles = append(archiveFiles, archives.FileInfo{`

```
     123 | 
     124 | 	if path != commonPath {
     125 | 		nameInArchive := strings.TrimPrefix(path, commonPath)
     126 | 		nameInArchive = strings.TrimPrefix(nameInArchive, string(filepath.Separator))
     127 | 		nameInArchive = filepath.ToSlash(nameInArchive)
     128 | 
>>   129 | 		archiveFiles = append(archiveFiles, archives.FileInfo{
>>   130 | 			FileInfo:      info,
>>   131 | 			NameInArchive: nameInArchive,
>>   132 | 			Open: func() (fs.File, error) {
>>   133 | 				return d.user.Fs.Open(path)
>>   134 | 			},
>>   135 | 		})
     136 | 	}
     137 | 
     138 | 	if info.IsDir() {
     139 | 		f, err := d.user.Fs.Open(path)
     140 | 		if err != nil {
     141 | 			return nil, err
```

- **to** (any): `http/raw.go` lines 205-205, starting at `if err := archiver.Archive(r.Context(), w, allFiles); err != nil {`

```
     199 | 	if len(filenames) > 1 {
     200 | 		name = "_" + name
     201 | 	}
     202 | 	name += extension
     203 | 	w.Header().Set("Content-Disposition", "attachment; filename*=utf-8''"+url.PathEscape(name))
     204 | 
>>   205 | 	if err := archiver.Archive(r.Context(), w, allFiles); err != nil {
     206 | 		return http.StatusInternalServerError, err
     207 | 	}
     208 | 
     209 | 	return 0, nil
     210 | }
     211 | 
```

## R010

- code: caddy, revision `base`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 215-215, starting at `rpHandler.HandleResponse = append(rpHandler.HandleResponse, goodResponseHandler)`

```
     209 | 
     210 | 	// note that when a response has any other status than 2xx, then we
     211 | 	// use the reverse proxy's default behaviour of copying the response
     212 | 	// back to the client, so we don't need to explicitly add a response
     213 | 	// handler specifically for that behaviour; we do need the 2xx handler
     214 | 	// though, to make handling fall through to handlers deeper in the chain.
>>   215 | 	rpHandler.HandleResponse = append(rpHandler.HandleResponse, goodResponseHandler)
     216 | 
     217 | 	// the rest of the config is specified by the user
     218 | 	// using the reverse_proxy directive syntax
     219 | 	dispenser.Next() // consume the directive name
     220 | 	err = rpHandler.UnmarshalCaddyfile(dispenser)
     221 | 	if err != nil {
```

- **to** (any): `modules/caddyhttp/headers/headers.go` lines 94-94, starting at `h.Request.ApplyToRequest(r)`

```
      88 | }
      89 | 
      90 | func (h Handler) ServeHTTP(w http.ResponseWriter, r *http.Request, next caddyhttp.Handler) error {
      91 | 	repl := r.Context().Value(caddy.ReplacerCtxKey).(*caddy.Replacer)
      92 | 
      93 | 	if h.Request != nil {
>>    94 | 		h.Request.ApplyToRequest(r)
      95 | 	}
      96 | 
      97 | 	if h.Response != nil {
      98 | 		if h.Response.Deferred || h.Response.Require != nil {
      99 | 			w = &responseWriterWrapper{
     100 | 				ResponseWriterWrapper: &caddyhttp.ResponseWriterWrapper{ResponseWriter: w},
```

## R011

- code: caddy, revision `head`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 240-240, starting at `rpHandler.HandleResponse = append(rpHandler.HandleResponse, goodResponseHandler)`

```
     234 | 
     235 | 	// note that when a response has any other status than 2xx, then we
     236 | 	// use the reverse proxy's default behaviour of copying the response
     237 | 	// back to the client, so we don't need to explicitly add a response
     238 | 	// handler specifically for that behaviour; we do need the 2xx handler
     239 | 	// though, to make handling fall through to handlers deeper in the chain.
>>   240 | 	rpHandler.HandleResponse = append(rpHandler.HandleResponse, goodResponseHandler)
     241 | 
     242 | 	// the rest of the config is specified by the user
     243 | 	// using the reverse_proxy directive syntax
     244 | 	dispenser.Next() // consume the directive name
     245 | 	err = rpHandler.UnmarshalCaddyfile(dispenser)
     246 | 	if err != nil {
```

- **to** (any): `modules/caddyhttp/headers/headers.go` lines 94-94, starting at `h.Request.ApplyToRequest(r)`

```
      88 | }
      89 | 
      90 | func (h Handler) ServeHTTP(w http.ResponseWriter, r *http.Request, next caddyhttp.Handler) error {
      91 | 	repl := r.Context().Value(caddy.ReplacerCtxKey).(*caddy.Replacer)
      92 | 
      93 | 	if h.Request != nil {
>>    94 | 		h.Request.ApplyToRequest(r)
      95 | 	}
      96 | 
      97 | 	if h.Response != nil {
      98 | 		if h.Response.Deferred || h.Response.Require != nil {
      99 | 			w = &responseWriterWrapper{
     100 | 				ResponseWriterWrapper: &caddyhttp.ResponseWriterWrapper{ResponseWriter: w},
```

## R012

- code: caddy, revision `head`
- relation `field_flow`: Value flowing through locals into a struct field. `from` defines a local variable; `to` is a keyed struct literal field f: e or a field store x.f = e; the value defined at `from` reaches e within the function (through local variables, and calls that derive their result from it).
- **from** (definition): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 210-210, starting at `placeholderName := "http.reverse_proxy.header." + http.CanonicalHeaderKey(from)`

```
     204 | 	// original request. We use vars matchers to test that the placeholder
     205 | 	// values aren't empty, because the header handler would not replace
     206 | 	// placeholders which have no value.
     207 | 	copyHeaderRoutes := []caddyhttp.Route{}
     208 | 	for _, from := range sortedHeadersToCopy {
     209 | 		to := http.CanonicalHeaderKey(headersToCopy[from])
>>   210 | 		placeholderName := "http.reverse_proxy.header." + http.CanonicalHeaderKey(from)
     211 | 		handler := &headers.Handler{
     212 | 			Request: &headers.HeaderOps{
     213 | 				Set: http.Header{
     214 | 					to: []string{"{" + placeholderName + "}"},
     215 | 				},
     216 | 			},
```

- **to** (keyed_field, field_store): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 213-213, starting at `Set: http.Header{`

```
     207 | 	copyHeaderRoutes := []caddyhttp.Route{}
     208 | 	for _, from := range sortedHeadersToCopy {
     209 | 		to := http.CanonicalHeaderKey(headersToCopy[from])
     210 | 		placeholderName := "http.reverse_proxy.header." + http.CanonicalHeaderKey(from)
     211 | 		handler := &headers.Handler{
     212 | 			Request: &headers.HeaderOps{
>>   213 | 				Set: http.Header{
     214 | 					to: []string{"{" + placeholderName + "}"},
     215 | 				},
     216 | 			},
     217 | 		}
     218 | 		copyHeaderRoutes = append(copyHeaderRoutes, caddyhttp.Route{
     219 | 			MatcherSetsRaw: []caddy.ModuleMap{{
```

## R013

- code: caddy, revision `base`
- relation `object_composition`: Object stored into a field or collection of another object. `from` defines an object (v := e) or modifies one through its variable (v.f = e); `to` is a field store x.g = e' that puts that object into x's field: the object is one of the stored values (for x.g = append(x.g, ...), one of the appended arguments) or a direct part of one (a literal element, a keyed value, an & operand or a call argument inside it). One composition step only: an object that reaches the stored value only through an earlier store does not count, and the container x itself is not stored.
- **from** (definition, field_store): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 185-189, starting at `handler := &headers.Handler{`

```
     179 | 		Match: &caddyhttp.ResponseMatcher{
     180 | 			StatusCode: []int{2},
     181 | 		},
     182 | 		Routes: []caddyhttp.Route{},
     183 | 	}
     184 | 
>>   185 | 	handler := &headers.Handler{
>>   186 | 		Request: &headers.HeaderOps{
>>   187 | 			Set: http.Header{},
>>   188 | 		},
>>   189 | 	}
     190 | 
     191 | 	// the list of headers to copy may be empty, but that's okay; we
     192 | 	// need at least one handler in the routes for the response handling
     193 | 	// logic in reverse_proxy to not skip this entry as empty.
     194 | 	for from, to := range headersToCopy {
     195 | 		handler.Request.Set.Set(to, "{http.reverse_proxy.header."+http.CanonicalHeaderKey(from)+"}")
```

- **to** (field_store): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 198-208, starting at `goodResponseHandler.Routes = append(`

```
     192 | 	// need at least one handler in the routes for the response handling
     193 | 	// logic in reverse_proxy to not skip this entry as empty.
     194 | 	for from, to := range headersToCopy {
     195 | 		handler.Request.Set.Set(to, "{http.reverse_proxy.header."+http.CanonicalHeaderKey(from)+"}")
     196 | 	}
     197 | 
>>   198 | 	goodResponseHandler.Routes = append(
>>   199 | 		goodResponseHandler.Routes,
>>   200 | 		caddyhttp.Route{
>>   201 | 			HandlersRaw: []json.RawMessage{caddyconfig.JSONModuleObject(
>>   202 | 				handler,
>>   203 | 				"handler",
>>   204 | 				"headers",
>>   205 | 				nil,
>>   206 | 			)},
>>   207 | 		},
>>   208 | 	)
     209 | 
     210 | 	// note that when a response has any other status than 2xx, then we
     211 | 	// use the reverse proxy's default behaviour of copying the response
     212 | 	// back to the client, so we don't need to explicitly add a response
     213 | 	// handler specifically for that behaviour; we do need the 2xx handler
     214 | 	// though, to make handling fall through to handlers deeper in the chain.
```

## R014

- code: filebrowser, revision `head`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `http/raw.go` lines 190-190, starting at `allFiles = append(allFiles, archiveFiles...)`

```
     184 | 	for _, fname := range filenames {
     185 | 		archiveFiles, err := getFiles(d, fname, commonDir)
     186 | 		if err != nil {
     187 | 			log.Printf("Failed to get files from %s: %v", fname, err)
     188 | 			continue
     189 | 		}
>>   190 | 		allFiles = append(allFiles, archiveFiles...)
     191 | 	}
     192 | 
     193 | 	name := filepath.Base(commonDir)
     194 | 	if name == "." || name == "" || name == string(filepath.Separator) {
     195 | 		if file.Name != "" {
     196 | 			name = file.Name
```

- **to** (any): `http/raw.go` lines 211-211, starting at `archiver.Archive(r.Context(), w, allFiles)`

```
     205 | 	if len(filenames) > 1 {
     206 | 		name = "_" + name
     207 | 	}
     208 | 	name += extension
     209 | 	w.Header().Set("Content-Disposition", "attachment; filename*=utf-8''"+url.PathEscape(name))
     210 | 
>>   211 | 	if err := archiver.Archive(r.Context(), w, allFiles); err != nil {
     212 | 		return http.StatusInternalServerError, err
     213 | 	}
     214 | 
     215 | 	return 0, nil
     216 | }
     217 | 
```

## R015

- code: filebrowser, revision `head`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `http/raw.go` lines 135-141, starting at `archiveFiles = append(archiveFiles, archives.FileInfo{`

```
     129 | 		// host a stored backslash survives and is emitted verbatim into the
     130 | 		// archive. Windows extractors then treat "\" as a path separator,
     131 | 		// allowing the entry to escape the extraction directory (zip-slip).
     132 | 		// Strip Windows separators regardless of host OS.
     133 | 		nameInArchive = strings.ReplaceAll(nameInArchive, "\\", "/")
     134 | 
>>   135 | 		archiveFiles = append(archiveFiles, archives.FileInfo{
>>   136 | 			FileInfo:      info,
>>   137 | 			NameInArchive: nameInArchive,
>>   138 | 			Open: func() (fs.File, error) {
>>   139 | 				return d.user.Fs.Open(path)
>>   140 | 			},
>>   141 | 		})
     142 | 	}
     143 | 
     144 | 	if info.IsDir() {
     145 | 		f, err := d.user.Fs.Open(path)
     146 | 		if err != nil {
     147 | 			return nil, err
```

- **to** (any): `http/raw.go` lines 211-211, starting at `if err := archiver.Archive(r.Context(), w, allFiles); err != nil {`

```
     205 | 	if len(filenames) > 1 {
     206 | 		name = "_" + name
     207 | 	}
     208 | 	name += extension
     209 | 	w.Header().Set("Content-Disposition", "attachment; filename*=utf-8''"+url.PathEscape(name))
     210 | 
>>   211 | 	if err := archiver.Archive(r.Context(), w, allFiles); err != nil {
     212 | 		return http.StatusInternalServerError, err
     213 | 	}
     214 | 
     215 | 	return 0, nil
     216 | }
     217 | 
```

## R016

- code: caddy, revision `head`
- relation `object_composition`: Object stored into a field or collection of another object. `from` defines an object (v := e) or modifies one through its variable (v.f = e); `to` is a field store x.g = e' that puts that object into x's field: the object is one of the stored values (for x.g = append(x.g, ...), one of the appended arguments) or a direct part of one (a literal element, a keyed value, an & operand or a call argument inside it). One composition step only: an object that reaches the stored value only through an earlier store does not count, and the container x itself is not stored.
- **from** (definition, field_store): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 218-230, starting at `copyHeaderRoutes = append(copyHeaderRoutes, caddyhttp.Route{`

```
     212 | 			Request: &headers.HeaderOps{
     213 | 				Set: http.Header{
     214 | 					to: []string{"{" + placeholderName + "}"},
     215 | 				},
     216 | 			},
     217 | 		}
>>   218 | 		copyHeaderRoutes = append(copyHeaderRoutes, caddyhttp.Route{
>>   219 | 			MatcherSetsRaw: []caddy.ModuleMap{{
>>   220 | 				"not": h.JSON(caddyhttp.MatchNot{MatcherSetsRaw: []caddy.ModuleMap{{
>>   221 | 					"vars": h.JSON(caddyhttp.VarsMatcher{"{" + placeholderName + "}": []string{""}}),
>>   222 | 				}}}),
>>   223 | 			}},
>>   224 | 			HandlersRaw: []json.RawMessage{caddyconfig.JSONModuleObject(
>>   225 | 				handler,
>>   226 | 				"handler",
>>   227 | 				"headers",
>>   228 | 				nil,
>>   229 | 			)},
>>   230 | 		})
     231 | 	}
     232 | 
     233 | 	goodResponseHandler.Routes = append(goodResponseHandler.Routes, copyHeaderRoutes...)
     234 | 
     235 | 	// note that when a response has any other status than 2xx, then we
     236 | 	// use the reverse proxy's default behaviour of copying the response
```

- **to** (field_store): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 233-233, starting at `goodResponseHandler.Routes = append(goodResponseHandler.Routes, copyHeaderRoutes...)`

```
     227 | 				"headers",
     228 | 				nil,
     229 | 			)},
     230 | 		})
     231 | 	}
     232 | 
>>   233 | 	goodResponseHandler.Routes = append(goodResponseHandler.Routes, copyHeaderRoutes...)
     234 | 
     235 | 	// note that when a response has any other status than 2xx, then we
     236 | 	// use the reverse proxy's default behaviour of copying the response
     237 | 	// back to the client, so we don't need to explicitly add a response
     238 | 	// handler specifically for that behaviour; we do need the 2xx handler
     239 | 	// though, to make handling fall through to handlers deeper in the chain.
```

## R017

- code: filebrowser, revision `base`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `http/raw.go` lines 178-185, starting at `archiveFiles, err := getFiles(d, fname, commonDir)`

```
     172 | 		return http.StatusInternalServerError, err
     173 | 	}
     174 | 
     175 | 	commonDir := fileutils.CommonPrefix(filepath.Separator, filenames...)
     176 | 
     177 | 	var allFiles []archives.FileInfo
>>   178 | 	for _, fname := range filenames {
>>   179 | 		archiveFiles, err := getFiles(d, fname, commonDir)
>>   180 | 		if err != nil {
>>   181 | 			log.Printf("Failed to get files from %s: %v", fname, err)
>>   182 | 			continue
>>   183 | 		}
>>   184 | 		allFiles = append(allFiles, archiveFiles...)
>>   185 | 	}
     186 | 
     187 | 	name := filepath.Base(commonDir)
     188 | 	if name == "." || name == "" || name == string(filepath.Separator) {
     189 | 		if file.Name != "" {
     190 | 			name = file.Name
     191 | 		} else {
```

- **to** (any): `http/raw.go` lines 125-125, starting at `nameInArchive := strings.TrimPrefix(path, commonPath)`

```
     119 | 		return nil, err
     120 | 	}
     121 | 
     122 | 	var archiveFiles []archives.FileInfo
     123 | 
     124 | 	if path != commonPath {
>>   125 | 		nameInArchive := strings.TrimPrefix(path, commonPath)
     126 | 		nameInArchive = strings.TrimPrefix(nameInArchive, string(filepath.Separator))
     127 | 		nameInArchive = filepath.ToSlash(nameInArchive)
     128 | 
     129 | 		archiveFiles = append(archiveFiles, archives.FileInfo{
     130 | 			FileInfo:      info,
     131 | 			NameInArchive: nameInArchive,
```

## R018

- code: filebrowser, revision `base`
- relation `field_flow`: Value flowing through locals into a struct field. `from` defines a local variable; `to` is a keyed struct literal field f: e or a field store x.f = e; the value defined at `from` reaches e within the function (through local variables, and calls that derive their result from it).
- **from** (definition): `http/raw.go` lines 125-127, starting at `nameInArchive = filepath.ToSlash(nameInArchive)`

```
     119 | 		return nil, err
     120 | 	}
     121 | 
     122 | 	var archiveFiles []archives.FileInfo
     123 | 
     124 | 	if path != commonPath {
>>   125 | 		nameInArchive := strings.TrimPrefix(path, commonPath)
>>   126 | 		nameInArchive = strings.TrimPrefix(nameInArchive, string(filepath.Separator))
>>   127 | 		nameInArchive = filepath.ToSlash(nameInArchive)
     128 | 
     129 | 		archiveFiles = append(archiveFiles, archives.FileInfo{
     130 | 			FileInfo:      info,
     131 | 			NameInArchive: nameInArchive,
     132 | 			Open: func() (fs.File, error) {
     133 | 				return d.user.Fs.Open(path)
```

- **to** (keyed_field, field_store): `http/raw.go` lines 129-135, starting at `NameInArchive: nameInArchive,`

```
     123 | 
     124 | 	if path != commonPath {
     125 | 		nameInArchive := strings.TrimPrefix(path, commonPath)
     126 | 		nameInArchive = strings.TrimPrefix(nameInArchive, string(filepath.Separator))
     127 | 		nameInArchive = filepath.ToSlash(nameInArchive)
     128 | 
>>   129 | 		archiveFiles = append(archiveFiles, archives.FileInfo{
>>   130 | 			FileInfo:      info,
>>   131 | 			NameInArchive: nameInArchive,
>>   132 | 			Open: func() (fs.File, error) {
>>   133 | 				return d.user.Fs.Open(path)
>>   134 | 			},
>>   135 | 		})
     136 | 	}
     137 | 
     138 | 	if info.IsDir() {
     139 | 		f, err := d.user.Fs.Open(path)
     140 | 		if err != nil {
     141 | 			return nil, err
```

## R019

- code: filebrowser, revision `head`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `http/raw.go` lines 185-185, starting at `archiveFiles, err := getFiles(d, fname, commonDir)`

```
     179 | 	}
     180 | 
     181 | 	commonDir := fileutils.CommonPrefix(filepath.Separator, filenames...)
     182 | 
     183 | 	var allFiles []archives.FileInfo
     184 | 	for _, fname := range filenames {
>>   185 | 		archiveFiles, err := getFiles(d, fname, commonDir)
     186 | 		if err != nil {
     187 | 			log.Printf("Failed to get files from %s: %v", fname, err)
     188 | 			continue
     189 | 		}
     190 | 		allFiles = append(allFiles, archiveFiles...)
     191 | 	}
```

- **to** (any): `http/raw.go` lines 133-133, starting at `nameInArchive = strings.ReplaceAll(nameInArchive, "\\", "/")`

```
     127 | 		nameInArchive = filepath.ToSlash(nameInArchive)
     128 | 		// filepath.ToSlash only rewrites the host separator, so on a Linux
     129 | 		// host a stored backslash survives and is emitted verbatim into the
     130 | 		// archive. Windows extractors then treat "\" as a path separator,
     131 | 		// allowing the entry to escape the extraction directory (zip-slip).
     132 | 		// Strip Windows separators regardless of host OS.
>>   133 | 		nameInArchive = strings.ReplaceAll(nameInArchive, "\\", "/")
     134 | 
     135 | 		archiveFiles = append(archiveFiles, archives.FileInfo{
     136 | 			FileInfo:      info,
     137 | 			NameInArchive: nameInArchive,
     138 | 			Open: func() (fs.File, error) {
     139 | 				return d.user.Fs.Open(path)
```

## R020

- code: filebrowser, revision `base`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `http/raw.go` lines 184-184, starting at `allFiles = append(allFiles, archiveFiles...)`

```
     178 | 	for _, fname := range filenames {
     179 | 		archiveFiles, err := getFiles(d, fname, commonDir)
     180 | 		if err != nil {
     181 | 			log.Printf("Failed to get files from %s: %v", fname, err)
     182 | 			continue
     183 | 		}
>>   184 | 		allFiles = append(allFiles, archiveFiles...)
     185 | 	}
     186 | 
     187 | 	name := filepath.Base(commonDir)
     188 | 	if name == "." || name == "" || name == string(filepath.Separator) {
     189 | 		if file.Name != "" {
     190 | 			name = file.Name
```

- **to** (any): `http/raw.go` lines 205-205, starting at `archiver.Archive(r.Context(), w, allFiles)`

```
     199 | 	if len(filenames) > 1 {
     200 | 		name = "_" + name
     201 | 	}
     202 | 	name += extension
     203 | 	w.Header().Set("Content-Disposition", "attachment; filename*=utf-8''"+url.PathEscape(name))
     204 | 
>>   205 | 	if err := archiver.Archive(r.Context(), w, allFiles); err != nil {
     206 | 		return http.StatusInternalServerError, err
     207 | 	}
     208 | 
     209 | 	return 0, nil
     210 | }
     211 | 
```

## R021

- code: filebrowser, revision `head`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `http/raw.go` lines 184-191, starting at `archiveFiles, err := getFiles(d, fname, commonDir)`

```
     178 | 		return http.StatusInternalServerError, err
     179 | 	}
     180 | 
     181 | 	commonDir := fileutils.CommonPrefix(filepath.Separator, filenames...)
     182 | 
     183 | 	var allFiles []archives.FileInfo
>>   184 | 	for _, fname := range filenames {
>>   185 | 		archiveFiles, err := getFiles(d, fname, commonDir)
>>   186 | 		if err != nil {
>>   187 | 			log.Printf("Failed to get files from %s: %v", fname, err)
>>   188 | 			continue
>>   189 | 		}
>>   190 | 		allFiles = append(allFiles, archiveFiles...)
>>   191 | 	}
     192 | 
     193 | 	name := filepath.Base(commonDir)
     194 | 	if name == "." || name == "" || name == string(filepath.Separator) {
     195 | 		if file.Name != "" {
     196 | 			name = file.Name
     197 | 		} else {
```

- **to** (any): `http/raw.go` lines 125-125, starting at `nameInArchive := strings.TrimPrefix(path, commonPath)`

```
     119 | 		return nil, err
     120 | 	}
     121 | 
     122 | 	var archiveFiles []archives.FileInfo
     123 | 
     124 | 	if path != commonPath {
>>   125 | 		nameInArchive := strings.TrimPrefix(path, commonPath)
     126 | 		nameInArchive = strings.TrimPrefix(nameInArchive, string(filepath.Separator))
     127 | 		nameInArchive = filepath.ToSlash(nameInArchive)
     128 | 		// filepath.ToSlash only rewrites the host separator, so on a Linux
     129 | 		// host a stored backslash survives and is emitted verbatim into the
     130 | 		// archive. Windows extractors then treat "\" as a path separator,
     131 | 		// allowing the entry to escape the extraction directory (zip-slip).
```

## R022

- code: caddy, revision `head`
- relation `field_flow`: Value flowing through locals into a struct field. `from` defines a local variable; `to` is a keyed struct literal field f: e or a field store x.f = e; the value defined at `from` reaches e within the function (through local variables, and calls that derive their result from it).
- **from** (definition): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 209-209, starting at `to := http.CanonicalHeaderKey(headersToCopy[from])`

```
     203 | 	// Set up handlers to copy headers from the auth response onto the
     204 | 	// original request. We use vars matchers to test that the placeholder
     205 | 	// values aren't empty, because the header handler would not replace
     206 | 	// placeholders which have no value.
     207 | 	copyHeaderRoutes := []caddyhttp.Route{}
     208 | 	for _, from := range sortedHeadersToCopy {
>>   209 | 		to := http.CanonicalHeaderKey(headersToCopy[from])
     210 | 		placeholderName := "http.reverse_proxy.header." + http.CanonicalHeaderKey(from)
     211 | 		handler := &headers.Handler{
     212 | 			Request: &headers.HeaderOps{
     213 | 				Set: http.Header{
     214 | 					to: []string{"{" + placeholderName + "}"},
     215 | 				},
```

- **to** (keyed_field, field_store): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 213-213, starting at `Set: http.Header{`

```
     207 | 	copyHeaderRoutes := []caddyhttp.Route{}
     208 | 	for _, from := range sortedHeadersToCopy {
     209 | 		to := http.CanonicalHeaderKey(headersToCopy[from])
     210 | 		placeholderName := "http.reverse_proxy.header." + http.CanonicalHeaderKey(from)
     211 | 		handler := &headers.Handler{
     212 | 			Request: &headers.HeaderOps{
>>   213 | 				Set: http.Header{
     214 | 					to: []string{"{" + placeholderName + "}"},
     215 | 				},
     216 | 			},
     217 | 		}
     218 | 		copyHeaderRoutes = append(copyHeaderRoutes, caddyhttp.Route{
     219 | 			MatcherSetsRaw: []caddy.ModuleMap{{
```

## R023

- code: caddy, revision `head`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 219-219, starting at `MatcherSetsRaw: []caddy.ModuleMap{{`

```
     213 | 				Set: http.Header{
     214 | 					to: []string{"{" + placeholderName + "}"},
     215 | 				},
     216 | 			},
     217 | 		}
     218 | 		copyHeaderRoutes = append(copyHeaderRoutes, caddyhttp.Route{
>>   219 | 			MatcherSetsRaw: []caddy.ModuleMap{{
     220 | 				"not": h.JSON(caddyhttp.MatchNot{MatcherSetsRaw: []caddy.ModuleMap{{
     221 | 					"vars": h.JSON(caddyhttp.VarsMatcher{"{" + placeholderName + "}": []string{""}}),
     222 | 				}}}),
     223 | 			}},
     224 | 			HandlersRaw: []json.RawMessage{caddyconfig.JSONModuleObject(
     225 | 				handler,
```

- **to** (any): `modules/caddyhttp/headers/headers.go` lines 94-94, starting at `h.Request.ApplyToRequest(r)`

```
      88 | }
      89 | 
      90 | func (h Handler) ServeHTTP(w http.ResponseWriter, r *http.Request, next caddyhttp.Handler) error {
      91 | 	repl := r.Context().Value(caddy.ReplacerCtxKey).(*caddy.Replacer)
      92 | 
      93 | 	if h.Request != nil {
>>    94 | 		h.Request.ApplyToRequest(r)
      95 | 	}
      96 | 
      97 | 	if h.Response != nil {
      98 | 		if h.Response.Deferred || h.Response.Require != nil {
      99 | 			w = &responseWriterWrapper{
     100 | 				ResponseWriterWrapper: &caddyhttp.ResponseWriterWrapper{ResponseWriter: w},
```

## R024

- code: caddy, revision `base`
- relation `object_composition`: Object stored into a field or collection of another object. `from` defines an object (v := e) or modifies one through its variable (v.f = e); `to` is a field store x.g = e' that puts that object into x's field: the object is one of the stored values (for x.g = append(x.g, ...), one of the appended arguments) or a direct part of one (a literal element, a keyed value, an & operand or a call argument inside it). One composition step only: an object that reaches the stored value only through an earlier store does not count, and the container x itself is not stored.
- **from** (definition, field_store): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 178-183, starting at `goodResponseHandler := caddyhttp.ResponseHandler{`

```
     172 | 
     173 | 	// set up handler for good responses; when a response
     174 | 	// has 2xx status, then we will copy some headers from
     175 | 	// the response onto the original request, and allow
     176 | 	// handling to continue down the middleware chain,
     177 | 	// by _not_ executing a terminal handler.
>>   178 | 	goodResponseHandler := caddyhttp.ResponseHandler{
>>   179 | 		Match: &caddyhttp.ResponseMatcher{
>>   180 | 			StatusCode: []int{2},
>>   181 | 		},
>>   182 | 		Routes: []caddyhttp.Route{},
>>   183 | 	}
     184 | 
     185 | 	handler := &headers.Handler{
     186 | 		Request: &headers.HeaderOps{
     187 | 			Set: http.Header{},
     188 | 		},
     189 | 	}
```

- **to** (field_store): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 215-215, starting at `rpHandler.HandleResponse = append(rpHandler.HandleResponse, goodResponseHandler)`

```
     209 | 
     210 | 	// note that when a response has any other status than 2xx, then we
     211 | 	// use the reverse proxy's default behaviour of copying the response
     212 | 	// back to the client, so we don't need to explicitly add a response
     213 | 	// handler specifically for that behaviour; we do need the 2xx handler
     214 | 	// though, to make handling fall through to handlers deeper in the chain.
>>   215 | 	rpHandler.HandleResponse = append(rpHandler.HandleResponse, goodResponseHandler)
     216 | 
     217 | 	// the rest of the config is specified by the user
     218 | 	// using the reverse_proxy directive syntax
     219 | 	dispenser.Next() // consume the directive name
     220 | 	err = rpHandler.UnmarshalCaddyfile(dispenser)
     221 | 	if err != nil {
```

## R025

- code: caddy, revision `base`
- relation `guard_property`: Condition that is a property of an object on the path, not on the flow. `from` is a keyed struct literal field anywhere inside the literal (through literal elements, keyed values and &) that initializes a local variable v; `to` is a field store v.f = e that reads that same definition of v.
- **from** (keyed_field): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 179-181, starting at `Match: &caddyhttp.ResponseMatcher{`

```
     173 | 	// set up handler for good responses; when a response
     174 | 	// has 2xx status, then we will copy some headers from
     175 | 	// the response onto the original request, and allow
     176 | 	// handling to continue down the middleware chain,
     177 | 	// by _not_ executing a terminal handler.
     178 | 	goodResponseHandler := caddyhttp.ResponseHandler{
>>   179 | 		Match: &caddyhttp.ResponseMatcher{
>>   180 | 			StatusCode: []int{2},
>>   181 | 		},
     182 | 		Routes: []caddyhttp.Route{},
     183 | 	}
     184 | 
     185 | 	handler := &headers.Handler{
     186 | 		Request: &headers.HeaderOps{
     187 | 			Set: http.Header{},
```

- **to** (field_store): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 198-208, starting at `goodResponseHandler.Routes = append(`

```
     192 | 	// need at least one handler in the routes for the response handling
     193 | 	// logic in reverse_proxy to not skip this entry as empty.
     194 | 	for from, to := range headersToCopy {
     195 | 		handler.Request.Set.Set(to, "{http.reverse_proxy.header."+http.CanonicalHeaderKey(from)+"}")
     196 | 	}
     197 | 
>>   198 | 	goodResponseHandler.Routes = append(
>>   199 | 		goodResponseHandler.Routes,
>>   200 | 		caddyhttp.Route{
>>   201 | 			HandlersRaw: []json.RawMessage{caddyconfig.JSONModuleObject(
>>   202 | 				handler,
>>   203 | 				"handler",
>>   204 | 				"headers",
>>   205 | 				nil,
>>   206 | 			)},
>>   207 | 		},
>>   208 | 	)
     209 | 
     210 | 	// note that when a response has any other status than 2xx, then we
     211 | 	// use the reverse proxy's default behaviour of copying the response
     212 | 	// back to the client, so we don't need to explicitly add a response
     213 | 	// handler specifically for that behaviour; we do need the 2xx handler
     214 | 	// though, to make handling fall through to handlers deeper in the chain.
```

## R026

- code: caddy, revision `head`
- relation `object_composition`: Object stored into a field or collection of another object. `from` defines an object (v := e) or modifies one through its variable (v.f = e); `to` is a field store x.g = e' that puts that object into x's field: the object is one of the stored values (for x.g = append(x.g, ...), one of the appended arguments) or a direct part of one (a literal element, a keyed value, an & operand or a call argument inside it). One composition step only: an object that reaches the stored value only through an earlier store does not count, and the container x itself is not stored.
- **from** (definition, field_store): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 180-194, starting at `goodResponseHandler := caddyhttp.ResponseHandler{`

```
     174 | 	// Set up handler for good responses; when a response has 2xx status,
     175 | 	// then we will copy some headers from the response onto the original
     176 | 	// request, and allow handling to continue down the middleware chain,
     177 | 	// by _not_ executing a terminal handler. We must have at least one
     178 | 	// route in the response handler, even if it's no-op, so that the
     179 | 	// response handling logic in reverse_proxy doesn't skip this entry.
>>   180 | 	goodResponseHandler := caddyhttp.ResponseHandler{
>>   181 | 		Match: &caddyhttp.ResponseMatcher{
>>   182 | 			StatusCode: []int{2},
>>   183 | 		},
>>   184 | 		Routes: []caddyhttp.Route{
>>   185 | 			{
>>   186 | 				HandlersRaw: []json.RawMessage{caddyconfig.JSONModuleObject(
>>   187 | 					&caddyhttp.VarsMiddleware{},
>>   188 | 					"handler",
>>   189 | 					"vars",
>>   190 | 					nil,
>>   191 | 				)},
>>   192 | 			},
>>   193 | 		},
>>   194 | 	}
     195 | 
     196 | 	// Sort the headers so that the order in the JSON output is deterministic.
     197 | 	sortedHeadersToCopy := make([]string, 0, len(headersToCopy))
     198 | 	for k := range headersToCopy {
     199 | 		sortedHeadersToCopy = append(sortedHeadersToCopy, k)
     200 | 	}
```

- **to** (field_store): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 240-240, starting at `rpHandler.HandleResponse = append(rpHandler.HandleResponse, goodResponseHandler)`

```
     234 | 
     235 | 	// note that when a response has any other status than 2xx, then we
     236 | 	// use the reverse proxy's default behaviour of copying the response
     237 | 	// back to the client, so we don't need to explicitly add a response
     238 | 	// handler specifically for that behaviour; we do need the 2xx handler
     239 | 	// though, to make handling fall through to handlers deeper in the chain.
>>   240 | 	rpHandler.HandleResponse = append(rpHandler.HandleResponse, goodResponseHandler)
     241 | 
     242 | 	// the rest of the config is specified by the user
     243 | 	// using the reverse_proxy directive syntax
     244 | 	dispenser.Next() // consume the directive name
     245 | 	err = rpHandler.UnmarshalCaddyfile(dispenser)
     246 | 	if err != nil {
```

## R027

- code: filebrowser, revision `head`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `http/raw.go` lines 135-135, starting at `archiveFiles = append(archiveFiles, archives.FileInfo{`

```
     129 | 		// host a stored backslash survives and is emitted verbatim into the
     130 | 		// archive. Windows extractors then treat "\" as a path separator,
     131 | 		// allowing the entry to escape the extraction directory (zip-slip).
     132 | 		// Strip Windows separators regardless of host OS.
     133 | 		nameInArchive = strings.ReplaceAll(nameInArchive, "\\", "/")
     134 | 
>>   135 | 		archiveFiles = append(archiveFiles, archives.FileInfo{
     136 | 			FileInfo:      info,
     137 | 			NameInArchive: nameInArchive,
     138 | 			Open: func() (fs.File, error) {
     139 | 				return d.user.Fs.Open(path)
     140 | 			},
     141 | 		})
```

- **to** (any): `http/raw.go` lines 190-190, starting at `allFiles = append(allFiles, archiveFiles...)`

```
     184 | 	for _, fname := range filenames {
     185 | 		archiveFiles, err := getFiles(d, fname, commonDir)
     186 | 		if err != nil {
     187 | 			log.Printf("Failed to get files from %s: %v", fname, err)
     188 | 			continue
     189 | 		}
>>   190 | 		allFiles = append(allFiles, archiveFiles...)
     191 | 	}
     192 | 
     193 | 	name := filepath.Base(commonDir)
     194 | 	if name == "." || name == "" || name == string(filepath.Separator) {
     195 | 		if file.Name != "" {
     196 | 			name = file.Name
```

## R028

- code: caddy, revision `head`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `modules/caddyhttp/reverseproxy/reverseproxy.go` lines 958-958, starting at `routeErr := rh.Routes.Compile(next).ServeHTTP(rw, origReq.WithContext(ctx))`

```
     952 | 			logger:   logger,
     953 | 		}
     954 | 		ctx := origReq.Context()
     955 | 		ctx = context.WithValue(ctx, proxyHandleResponseContextCtxKey, hrc)
     956 | 
     957 | 		// pass the request through the response handler routes
>>   958 | 		routeErr := rh.Routes.Compile(next).ServeHTTP(rw, origReq.WithContext(ctx))
     959 | 
     960 | 		// close the response body afterwards, since we don't need it anymore;
     961 | 		// either a route had 'copy_response' which already consumed the body,
     962 | 		// or some other terminal handler ran which doesn't need the response
     963 | 		// body after that point (e.g. 'file_server' for X-Accel-Redirect flow),
     964 | 		// or we fell through to subsequent handlers past this proxy
```

- **to** (any): `modules/caddyhttp/headers/headers.go` lines 94-94, starting at `h.Request.ApplyToRequest(r)`

```
      88 | }
      89 | 
      90 | func (h Handler) ServeHTTP(w http.ResponseWriter, r *http.Request, next caddyhttp.Handler) error {
      91 | 	repl := r.Context().Value(caddy.ReplacerCtxKey).(*caddy.Replacer)
      92 | 
      93 | 	if h.Request != nil {
>>    94 | 		h.Request.ApplyToRequest(r)
      95 | 	}
      96 | 
      97 | 	if h.Response != nil {
      98 | 		if h.Response.Deferred || h.Response.Require != nil {
      99 | 			w = &responseWriterWrapper{
     100 | 				ResponseWriterWrapper: &caddyhttp.ResponseWriterWrapper{ResponseWriter: w},
```

## R029

- code: caddy, revision `head`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 240-240, starting at `rpHandler.HandleResponse = append(rpHandler.HandleResponse, goodResponseHandler)`

```
     234 | 
     235 | 	// note that when a response has any other status than 2xx, then we
     236 | 	// use the reverse proxy's default behaviour of copying the response
     237 | 	// back to the client, so we don't need to explicitly add a response
     238 | 	// handler specifically for that behaviour; we do need the 2xx handler
     239 | 	// though, to make handling fall through to handlers deeper in the chain.
>>   240 | 	rpHandler.HandleResponse = append(rpHandler.HandleResponse, goodResponseHandler)
     241 | 
     242 | 	// the rest of the config is specified by the user
     243 | 	// using the reverse_proxy directive syntax
     244 | 	dispenser.Next() // consume the directive name
     245 | 	err = rpHandler.UnmarshalCaddyfile(dispenser)
     246 | 	if err != nil {
```

- **to** (any): `modules/caddyhttp/reverseproxy/reverseproxy.go` lines 958-958, starting at `routeErr := rh.Routes.Compile(next).ServeHTTP(rw, origReq.WithContext(ctx))`

```
     952 | 			logger:   logger,
     953 | 		}
     954 | 		ctx := origReq.Context()
     955 | 		ctx = context.WithValue(ctx, proxyHandleResponseContextCtxKey, hrc)
     956 | 
     957 | 		// pass the request through the response handler routes
>>   958 | 		routeErr := rh.Routes.Compile(next).ServeHTTP(rw, origReq.WithContext(ctx))
     959 | 
     960 | 		// close the response body afterwards, since we don't need it anymore;
     961 | 		// either a route had 'copy_response' which already consumed the body,
     962 | 		// or some other terminal handler ran which doesn't need the response
     963 | 		// body after that point (e.g. 'file_server' for X-Accel-Redirect flow),
     964 | 		// or we fell through to subsequent handlers past this proxy
```

## R030

- code: caddy, revision `head`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 211-217, starting at `handler := &headers.Handler{`

```
     205 | 	// values aren't empty, because the header handler would not replace
     206 | 	// placeholders which have no value.
     207 | 	copyHeaderRoutes := []caddyhttp.Route{}
     208 | 	for _, from := range sortedHeadersToCopy {
     209 | 		to := http.CanonicalHeaderKey(headersToCopy[from])
     210 | 		placeholderName := "http.reverse_proxy.header." + http.CanonicalHeaderKey(from)
>>   211 | 		handler := &headers.Handler{
>>   212 | 			Request: &headers.HeaderOps{
>>   213 | 				Set: http.Header{
>>   214 | 					to: []string{"{" + placeholderName + "}"},
>>   215 | 				},
>>   216 | 			},
>>   217 | 		}
     218 | 		copyHeaderRoutes = append(copyHeaderRoutes, caddyhttp.Route{
     219 | 			MatcherSetsRaw: []caddy.ModuleMap{{
     220 | 				"not": h.JSON(caddyhttp.MatchNot{MatcherSetsRaw: []caddy.ModuleMap{{
     221 | 					"vars": h.JSON(caddyhttp.VarsMatcher{"{" + placeholderName + "}": []string{""}}),
     222 | 				}}}),
     223 | 			}},
```

- **to** (any): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 224-229, starting at `HandlersRaw: []json.RawMessage{caddyconfig.JSONModuleObject( handler, "handler", "headers", nil, )},`

```
     218 | 		copyHeaderRoutes = append(copyHeaderRoutes, caddyhttp.Route{
     219 | 			MatcherSetsRaw: []caddy.ModuleMap{{
     220 | 				"not": h.JSON(caddyhttp.MatchNot{MatcherSetsRaw: []caddy.ModuleMap{{
     221 | 					"vars": h.JSON(caddyhttp.VarsMatcher{"{" + placeholderName + "}": []string{""}}),
     222 | 				}}}),
     223 | 			}},
>>   224 | 			HandlersRaw: []json.RawMessage{caddyconfig.JSONModuleObject(
>>   225 | 				handler,
>>   226 | 				"handler",
>>   227 | 				"headers",
>>   228 | 				nil,
>>   229 | 			)},
     230 | 		})
     231 | 	}
     232 | 
     233 | 	goodResponseHandler.Routes = append(goodResponseHandler.Routes, copyHeaderRoutes...)
     234 | 
     235 | 	// note that when a response has any other status than 2xx, then we
```

## R031

- code: caddy, revision `head`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 240-240, starting at `rpHandler.HandleResponse = append(rpHandler.HandleResponse, goodResponseHandler)`

```
     234 | 
     235 | 	// note that when a response has any other status than 2xx, then we
     236 | 	// use the reverse proxy's default behaviour of copying the response
     237 | 	// back to the client, so we don't need to explicitly add a response
     238 | 	// handler specifically for that behaviour; we do need the 2xx handler
     239 | 	// though, to make handling fall through to handlers deeper in the chain.
>>   240 | 	rpHandler.HandleResponse = append(rpHandler.HandleResponse, goodResponseHandler)
     241 | 
     242 | 	// the rest of the config is specified by the user
     243 | 	// using the reverse_proxy directive syntax
     244 | 	dispenser.Next() // consume the directive name
     245 | 	err = rpHandler.UnmarshalCaddyfile(dispenser)
     246 | 	if err != nil {
```

- **to** (any): `modules/caddyhttp/headers/headers.go` lines 93-95, starting at `if h.Request != nil {`

```
      87 | 	return nil
      88 | }
      89 | 
      90 | func (h Handler) ServeHTTP(w http.ResponseWriter, r *http.Request, next caddyhttp.Handler) error {
      91 | 	repl := r.Context().Value(caddy.ReplacerCtxKey).(*caddy.Replacer)
      92 | 
>>    93 | 	if h.Request != nil {
>>    94 | 		h.Request.ApplyToRequest(r)
>>    95 | 	}
      96 | 
      97 | 	if h.Response != nil {
      98 | 		if h.Response.Deferred || h.Response.Require != nil {
      99 | 			w = &responseWriterWrapper{
     100 | 				ResponseWriterWrapper: &caddyhttp.ResponseWriterWrapper{ResponseWriter: w},
     101 | 				replacer:              repl,
```

## R032

- code: caddy, revision `head`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 219-223, starting at `MatcherSetsRaw: []caddy.ModuleMap{{ "not": h.JSON(caddyhttp.MatchNot{MatcherSetsRaw: []caddy.ModuleMap{{ "vars": h.JSON(caddyhttp.VarsMatcher{"{" + placeholderName + "}": []string{""}}), }}}), }},`

```
     213 | 				Set: http.Header{
     214 | 					to: []string{"{" + placeholderName + "}"},
     215 | 				},
     216 | 			},
     217 | 		}
     218 | 		copyHeaderRoutes = append(copyHeaderRoutes, caddyhttp.Route{
>>   219 | 			MatcherSetsRaw: []caddy.ModuleMap{{
>>   220 | 				"not": h.JSON(caddyhttp.MatchNot{MatcherSetsRaw: []caddy.ModuleMap{{
>>   221 | 					"vars": h.JSON(caddyhttp.VarsMatcher{"{" + placeholderName + "}": []string{""}}),
>>   222 | 				}}}),
>>   223 | 			}},
     224 | 			HandlersRaw: []json.RawMessage{caddyconfig.JSONModuleObject(
     225 | 				handler,
     226 | 				"handler",
     227 | 				"headers",
     228 | 				nil,
     229 | 			)},
```

- **to** (any): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 224-229, starting at `HandlersRaw: []json.RawMessage{caddyconfig.JSONModuleObject( handler, "handler", "headers", nil, )},`

```
     218 | 		copyHeaderRoutes = append(copyHeaderRoutes, caddyhttp.Route{
     219 | 			MatcherSetsRaw: []caddy.ModuleMap{{
     220 | 				"not": h.JSON(caddyhttp.MatchNot{MatcherSetsRaw: []caddy.ModuleMap{{
     221 | 					"vars": h.JSON(caddyhttp.VarsMatcher{"{" + placeholderName + "}": []string{""}}),
     222 | 				}}}),
     223 | 			}},
>>   224 | 			HandlersRaw: []json.RawMessage{caddyconfig.JSONModuleObject(
>>   225 | 				handler,
>>   226 | 				"handler",
>>   227 | 				"headers",
>>   228 | 				nil,
>>   229 | 			)},
     230 | 		})
     231 | 	}
     232 | 
     233 | 	goodResponseHandler.Routes = append(goodResponseHandler.Routes, copyHeaderRoutes...)
     234 | 
     235 | 	// note that when a response has any other status than 2xx, then we
```

## R033

- code: caddy, revision `head`
- relation `object_composition`: Object stored into a field or collection of another object. `from` defines an object (v := e) or modifies one through its variable (v.f = e); `to` is a field store x.g = e' that puts that object into x's field: the object is one of the stored values (for x.g = append(x.g, ...), one of the appended arguments) or a direct part of one (a literal element, a keyed value, an & operand or a call argument inside it). One composition step only: an object that reaches the stored value only through an earlier store does not count, and the container x itself is not stored.
- **from** (definition, field_store): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 211-217, starting at `handler := &headers.Handler{`

```
     205 | 	// values aren't empty, because the header handler would not replace
     206 | 	// placeholders which have no value.
     207 | 	copyHeaderRoutes := []caddyhttp.Route{}
     208 | 	for _, from := range sortedHeadersToCopy {
     209 | 		to := http.CanonicalHeaderKey(headersToCopy[from])
     210 | 		placeholderName := "http.reverse_proxy.header." + http.CanonicalHeaderKey(from)
>>   211 | 		handler := &headers.Handler{
>>   212 | 			Request: &headers.HeaderOps{
>>   213 | 				Set: http.Header{
>>   214 | 					to: []string{"{" + placeholderName + "}"},
>>   215 | 				},
>>   216 | 			},
>>   217 | 		}
     218 | 		copyHeaderRoutes = append(copyHeaderRoutes, caddyhttp.Route{
     219 | 			MatcherSetsRaw: []caddy.ModuleMap{{
     220 | 				"not": h.JSON(caddyhttp.MatchNot{MatcherSetsRaw: []caddy.ModuleMap{{
     221 | 					"vars": h.JSON(caddyhttp.VarsMatcher{"{" + placeholderName + "}": []string{""}}),
     222 | 				}}}),
     223 | 			}},
```

- **to** (field_store): `modules/caddyhttp/reverseproxy/forwardauth/caddyfile.go` lines 233-233, starting at `goodResponseHandler.Routes = append(goodResponseHandler.Routes, copyHeaderRoutes...)`

```
     227 | 				"headers",
     228 | 				nil,
     229 | 			)},
     230 | 		})
     231 | 	}
     232 | 
>>   233 | 	goodResponseHandler.Routes = append(goodResponseHandler.Routes, copyHeaderRoutes...)
     234 | 
     235 | 	// note that when a response has any other status than 2xx, then we
     236 | 	// use the reverse proxy's default behaviour of copying the response
     237 | 	// back to the client, so we don't need to explicitly add a response
     238 | 	// handler specifically for that behaviour; we do need the 2xx handler
     239 | 	// though, to make handling fall through to handlers deeper in the chain.
```

## R034

- code: filebrowser, revision `base`
- relation `unsupported`: A link that none of the relations above describes (for example one made at run time by a framework). It is recorded as you state it; no relation-specific meaning is attached to it.
- **from** (any): `http/raw.go` lines 129-129, starting at `archiveFiles = append(archiveFiles, archives.FileInfo{`

```
     123 | 
     124 | 	if path != commonPath {
     125 | 		nameInArchive := strings.TrimPrefix(path, commonPath)
     126 | 		nameInArchive = strings.TrimPrefix(nameInArchive, string(filepath.Separator))
     127 | 		nameInArchive = filepath.ToSlash(nameInArchive)
     128 | 
>>   129 | 		archiveFiles = append(archiveFiles, archives.FileInfo{
     130 | 			FileInfo:      info,
     131 | 			NameInArchive: nameInArchive,
     132 | 			Open: func() (fs.File, error) {
     133 | 				return d.user.Fs.Open(path)
     134 | 			},
     135 | 		})
```

- **to** (any): `http/raw.go` lines 184-184, starting at `allFiles = append(allFiles, archiveFiles...)`

```
     178 | 	for _, fname := range filenames {
     179 | 		archiveFiles, err := getFiles(d, fname, commonDir)
     180 | 		if err != nil {
     181 | 			log.Printf("Failed to get files from %s: %v", fname, err)
     182 | 			continue
     183 | 		}
>>   184 | 		allFiles = append(allFiles, archiveFiles...)
     185 | 	}
     186 | 
     187 | 	name := filepath.Base(commonDir)
     188 | 	if name == "." || name == "" || name == string(filepath.Separator) {
     189 | 		if file.Name != "" {
     190 | 			name = file.Name
```

## R035

- code: filebrowser, revision `head`
- relation `field_flow`: Value flowing through locals into a struct field. `from` defines a local variable; `to` is a keyed struct literal field f: e or a field store x.f = e; the value defined at `from` reaches e within the function (through local variables, and calls that derive their result from it).
- **from** (definition): `http/raw.go` lines 125-133, starting at `nameInArchive = strings.ReplaceAll(nameInArchive, "\\", "/")`

```
     119 | 		return nil, err
     120 | 	}
     121 | 
     122 | 	var archiveFiles []archives.FileInfo
     123 | 
     124 | 	if path != commonPath {
>>   125 | 		nameInArchive := strings.TrimPrefix(path, commonPath)
>>   126 | 		nameInArchive = strings.TrimPrefix(nameInArchive, string(filepath.Separator))
>>   127 | 		nameInArchive = filepath.ToSlash(nameInArchive)
>>   128 | 		// filepath.ToSlash only rewrites the host separator, so on a Linux
>>   129 | 		// host a stored backslash survives and is emitted verbatim into the
>>   130 | 		// archive. Windows extractors then treat "\" as a path separator,
>>   131 | 		// allowing the entry to escape the extraction directory (zip-slip).
>>   132 | 		// Strip Windows separators regardless of host OS.
>>   133 | 		nameInArchive = strings.ReplaceAll(nameInArchive, "\\", "/")
     134 | 
     135 | 		archiveFiles = append(archiveFiles, archives.FileInfo{
     136 | 			FileInfo:      info,
     137 | 			NameInArchive: nameInArchive,
     138 | 			Open: func() (fs.File, error) {
     139 | 				return d.user.Fs.Open(path)
```

- **to** (keyed_field, field_store): `http/raw.go` lines 135-141, starting at `NameInArchive: nameInArchive,`

```
     129 | 		// host a stored backslash survives and is emitted verbatim into the
     130 | 		// archive. Windows extractors then treat "\" as a path separator,
     131 | 		// allowing the entry to escape the extraction directory (zip-slip).
     132 | 		// Strip Windows separators regardless of host OS.
     133 | 		nameInArchive = strings.ReplaceAll(nameInArchive, "\\", "/")
     134 | 
>>   135 | 		archiveFiles = append(archiveFiles, archives.FileInfo{
>>   136 | 			FileInfo:      info,
>>   137 | 			NameInArchive: nameInArchive,
>>   138 | 			Open: func() (fs.File, error) {
>>   139 | 				return d.user.Fs.Open(path)
>>   140 | 			},
>>   141 | 		})
     142 | 	}
     143 | 
     144 | 	if info.IsDir() {
     145 | 		f, err := d.user.Fs.Open(path)
     146 | 		if err != nil {
     147 | 			return nil, err
```

