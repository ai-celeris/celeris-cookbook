# Embeddable demo builds

Build output for the interactive demos shown on the published cookbook pages.
Every app in `examples/` that runs in a browser is built here into a
self-contained static page under `dist/<name>/`, which the docs site serves at
`/cookbook-demos/<name>/` and embeds in an iframe on that example's page.

This directory is a build target, not an example. The apps themselves live in
`examples/`, and running them there is unchanged.

## Build

```sh
npm ci --prefix examples/burst-rendering
node demos/build.mjs
node --test demos/build.test.mjs
```

`dist/` is ignored build output. Cookbook CI builds and browser-tests it from
the example source. The Celeris docs deployment repeats that build from the
cookbook revision pinned by its submodule before publishing the pages.

## How an embedded page differs from the standalone one

1. `window.__CELERIS_DEMO__.apiBase` points at the shared proxy endpoint
   instead of the example's own local server. The apps read it with a fallback
   to their local route, so nothing changes when you run them yourself.
2. `<body data-embed>` hides the standalone page header, because the docs page
   already introduces the app.
3. The chatbot's "use your own API key" panel is removed. The docs content
   security policy allows same-origin connections only, and a docs page is the
   wrong place to invite pasting a key.
4. `embed.js` reports the page height to the host and follows the docs light or
   dark theme.

The hosted inference demos call a same-origin endpoint and never carry an API
key in the browser. Standalone examples continue to use their own local server.
