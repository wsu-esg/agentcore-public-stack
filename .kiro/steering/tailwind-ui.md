---
inclusion: fileMatch
fileMatchPattern: "**/*.{html,css,ts,component.ts,page.ts}"
---

# Tailwind CSS v4.1 Best Practices

Apply these patterns when working with HTML, CSS, styling, accessibility, theming, or building UI components.

## Quick Reference

### v4.1 Critical Changes

Never use deprecated utilities — always use replacements:

| Deprecated | Replacement |
|------------|-------------|
| `bg-opacity-*` | `bg-black/50` (opacity modifier) |
| `bg-gradient-*` | `bg-linear-*` |
| `shadow-sm` | `shadow-xs` |
| `shadow` | `shadow-sm` |
| `rounded-sm` | `rounded-xs` |
| `rounded` | `rounded-sm` |
| `ring` | `ring-3` |
| `outline-none` | `outline-hidden` |
| `leading-*` | Use `text-base/7` line-height modifiers |
| `flex-shrink-*` / `flex-grow-*` | `shrink-*` / `grow-*` |
| `space-x-*` in flex/grid | Use `gap-*` instead |

### Essential Patterns

```html
<!-- Gap over space utilities -->
<div class="flex gap-4">...</div>

<!-- Opacity modifiers -->
<div class="bg-primary-500/60">...</div>

<!-- Line height modifiers -->
<p class="text-base/7">...</p>

<!-- Dynamic viewport height (mobile-safe) -->
<div class="min-h-dvh">...</div>

<!-- Size utility for equal dimensions -->
<div class="size-12">...</div>
```

## Reference Documentation

For detailed patterns, see:

- **v4 Migration** — #[[file:tailwind-v4-migration.md]]
  - Full breaking changes, upgrade process, new features
  
- **Accessibility** — #[[file:tailwind-accessibility.md]]
  - WCAG 2.1 AA patterns: contrast, focus, screen readers
  
- **Theming** — #[[file:tailwind-theming.md]]
  - @theme setup, CSS variables, light/dark mode
  
- **Components** — #[[file:tailwind-components.md]]
  - Accessible component patterns (buttons, forms, cards, nav)

## Core Principles

1. **Use Tailwind's scale** — Avoid arbitrary values like `ml-[16px]`; use `ml-4`
2. **Never use @apply** — Use CSS variables or framework components
3. **Gap over margins** — Use `gap-*` in flex/grid, not `space-*` or child margins
4. **Test both modes** — Always verify light AND dark mode appearance
5. **Accessibility first** — Every interactive element needs visible focus states and proper contrast

## Common Patterns

### Focus States

```html
<button class="focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2">
  Accessible button
</button>
```

### Dark Mode

```html
<div class="bg-white text-gray-900 dark:bg-gray-900 dark:text-white">
  Mode-aware content
</div>
```

### Responsive Design

```html
<!-- Only add breakpoints when values change -->
<div class="px-4 lg:px-8">...</div>
```

## Accessibility Checklist

- [ ] Color contrast meets 4.5:1 for text, 3:1 for UI
- [ ] All interactive elements have visible focus states
- [ ] Icon buttons have accessible labels (sr-only)
- [ ] Form inputs have associated labels
- [ ] Animations respect `prefers-reduced-motion`
- [ ] Touch targets are at least 44×44px
- [ ] Both light and dark modes are fully styled
