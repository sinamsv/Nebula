# web_frontend/app/globals.css -- additions

Append this block at the end of the file (after the existing
`.markdown-body` rules). This makes list markers, blockquote borders,
and text-alignment inside a markdown-rendered assistant reply flip
correctly when the browser resolves that block's direction to RTL via
`dir="auto"` (set in MessageBubble.tsx).

```css
/* RTL support: dir="auto" on .markdown-body (see MessageBubble.tsx)
   resolves per-message based on content, but list bullets/numbers and
   blockquote borders don't automatically mirror themselves the way
   plain text does -- these rules make them follow whatever direction
   the browser resolved for that specific block. */
.markdown-body[dir="rtl"] {
  text-align: right;
}
.markdown-body[dir="rtl"] ul,
.markdown-body[dir="rtl"] ol {
  margin-left: 0;
  margin-right: 1.25em;
}
.markdown-body[dir="rtl"] blockquote {
  border-left: none;
  border-right: 3px solid rgba(255, 255, 255, 0.15);
  padding-left: 0;
  padding-right: 1em;
}
```

Note: `dir="auto"` computes the resolved direction and reflects it back
as an actual `dir="rtl"` or `dir="ltr"` attribute on the element in the
DOM (this is standard browser behavior, not something we compute
ourselves) -- which is exactly what the `[dir="rtl"]` attribute
selectors above key off of.
