---
name: liquidglass
description: Apply Apple-style "liquid glass" effects (realistic WebGL refraction, blur, chromatic aberration, Fresnel lighting, specular highlights) to any HTML element using the @ybouane/liquidglass library. Use when the user wants glassmorphism, frosted/liquid glass panels, glass cards or navbars, or iOS 26 style translucent UI on a web page, site, or HTML artifact.
---

# LiquidGlass

A liquid glass effect library for the web by ybouane (https://github.com/ybouane/liquidglass, MIT).
It applies realistic glass refraction, blur, chromatic aberration, and lighting to any HTML
element using WebGL shaders — far more realistic than plain CSS `backdrop-filter` glassmorphism.

Live demo: https://liquid-glass.ybouane.com/

## When to use

- The user asks for "liquid glass", "glassmorphism", frosted glass panels, glass cards/navbars,
  or Apple/iOS-style translucent UI on a web page.
- Prefer this library when realism matters (refraction that bends the background, edge
  highlights, chromatic aberration). For a subtle static frost, plain CSS
  `backdrop-filter: blur()` may be enough and is cheaper.

## How to use it in a page

Import from the CDN (no build step needed):

```html
<script type="module">
  import { LiquidGlass } from 'https://cdn.jsdelivr.net/npm/@ybouane/liquidglass/dist/index.js';

  const instance = await LiquidGlass.init({
    root: document.querySelector('#root'),          // container element
    glassElements: document.querySelectorAll('.glass'), // must be DIRECT children of root
    defaults: { blurAmount: 0.2 },                  // optional per-instance defaults
  });
</script>
```

Or via npm: `npm install @ybouane/liquidglass` then `import { LiquidGlass } from '@ybouane/liquidglass'`.

Key rules (see README.md in this skill for the full API and option table):

- Glass elements must be **direct children** of the `root` container; the rest of the root's
  content (siblings) is what gets captured and refracted behind them.
- Content that animates or changes needs `data-dynamic` on the element (videos are handled
  automatically); otherwise it is captured once and cached. Call `instance.markChanged(el)`
  for changes the library can't observe.
- Per-element tuning goes in `data-config` (JSON) — e.g.
  `{"floating": true, "blurAmount": 0.25}`.
- `instance.destroy()` tears everything down; `invalidateFontEmbedCache()` after loading
  new webfonts.
- Note the limitations section in README.md (structure, performance, text/font capture)
  before promising pixel-perfect results; heavy pages should keep glass panels few and small.
- CSP caveat: pages that block external scripts (e.g. claude.ai Artifacts) cannot load the
  CDN module — there, either inline the bundled library (`npm install @ybouane/liquidglass`
  and embed `node_modules/@ybouane/liquidglass/dist/index.js`) or fall back to a CSS-only
  glassmorphism approximation (`backdrop-filter: blur() saturate()`, translucent background,
  1px light inner border, soft shadow).

## Files in this skill

- `README.md` — full upstream documentation: API, all config options, attributes, stacking,
  limitations, browser support. Read this before writing code that uses the library.
- `defaults.ts` — the library's per-element config defaults, for exact option names and values.
- Full source and demo page: https://github.com/ybouane/liquidglass
