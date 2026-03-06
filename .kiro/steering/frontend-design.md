---
inclusion: fileMatch
fileMatchPattern: ['**/*.html', '**/*.css', '**/*.ts', 'src/app/**/*']
---

# Frontend Design Principles

Apply these principles when building Angular components, pages, and dashboards for the AgentCore AI platform. Create distinctive, production-grade interfaces that avoid generic AI aesthetics while maintaining accessibility and usability.

## Design Context

This is an enterprise AI agent platform with:
- **Users**: Technical professionals, researchers, developers
- **Core interactions**: Chat interfaces, data visualization, admin dashboards
- **Brand tone**: Professional, intelligent, trustworthy, innovative
- **Technical stack**: Angular 21 standalone components + Tailwind CSS v4.1 + Signals

## Design Thinking Process

Before implementing any component, define:

### 1. Component Purpose
- What user problem does this solve?
- What's the primary user action or goal?
- How does it fit into the broader user journey?

### 2. Aesthetic Direction

Choose ONE direction and commit fully:

**For AI/Technical Interfaces**:
- **Brutally minimal** — Essential information, maximum clarity, generous whitespace
- **Data-forward** — Typography-driven, grid-based, content hierarchy
- **Technical/utilitarian** — Functional, precise, purposeful
- **Refined/sophisticated** — Elegant, premium, professional

**For Dashboards/Analytics**:
- **Editorial/magazine** — Bold typography, strong grid, visual hierarchy
- **Geometric/structured** — Symmetry, patterns, organized complexity
- **Monochromatic depth** — Layered grays, subtle shadows, depth through tone

**For Marketing/Landing**:
- **Retro-futuristic** — Nostalgic tech with modern polish
- **Organic/flowing** — Curved forms, natural motion
- **Maximalist** — Rich, layered, visually dense (use sparingly)

### 3. Technical Constraints
- Angular OnPush change detection (use signals)
- Tailwind CSS v4.1 utilities only (no custom CSS unless necessary)
- WCAG 2.1 AA accessibility compliance
- Light/dark mode support required
- Mobile-first responsive design

### 4. Differentiation
- What makes this component memorable?
- What unexpected detail elevates the experience?
- How does it feel distinctly "AgentCore"?

**CRITICAL**: Intentionality over intensity. A refined minimal design executed perfectly beats a chaotic maximalist design done poorly.

## Angular + Tailwind Implementation Standards

### Component Structure

Use Angular 21 standalone components with OnPush change detection:

```typescript
@Component({
  selector: 'app-feature-name',
  standalone: true,
  imports: [CommonModule, /* other imports */],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <!-- Use Tailwind utilities directly in template -->
    <div class="flex flex-col gap-4 p-6">
      @if (isLoading()) {
        <app-loading-spinner />
      } @else {
        <h2 class="text-2xl/8 font-semibold text-gray-900 dark:text-white">
          {{ title() }}
        </h2>
      }
    </div>
  `,
})
export class FeatureNameComponent {
  // Use signals for reactive state
  readonly isLoading = signal(false);
  readonly title = signal('Feature Title');
  
  // Use computed for derived state
  readonly displayText = computed(() => 
    this.isLoading() ? 'Loading...' : this.title()
  );
}
```

### Tailwind CSS v4.1 Patterns

**ALWAYS use Tailwind utilities** — avoid custom CSS unless absolutely necessary:

```html
<!-- ✅ CORRECT: Tailwind utilities -->
<div class="flex items-center gap-3 rounded-sm bg-white p-4 shadow-sm dark:bg-gray-800">
  <span class="text-sm/6 text-gray-600 dark:text-gray-300">Content</span>
</div>

<!-- ❌ AVOID: Custom CSS classes -->
<div class="custom-card">
  <span class="custom-text">Content</span>
</div>
```

**Key Tailwind v4.1 patterns**:
- Use `gap-*` instead of `space-*` in flex/grid layouts
- Use `text-base/7` for font size with line height (not separate `leading-*`)
- Use `min-h-dvh` instead of `min-h-screen` for mobile compatibility
- Use `size-12` instead of `h-12 w-12` for equal dimensions
- Always include dark mode variants: `dark:bg-gray-900 dark:text-white`

### Typography

**System font stack** (already configured in project):
```css
/* Default body font - clean, professional */
font-family: system-ui, -apple-system, sans-serif;
```

**For distinctive headings**, use Tailwind's font utilities:
```html
<!-- Large, bold headings -->
<h1 class="text-4xl/tight font-bold tracking-tight">Main Heading</h1>

<!-- Refined subheadings -->
<h2 class="text-2xl/8 font-semibold tracking-tight">Subheading</h2>

<!-- Monospace for code/technical content -->
<code class="font-mono text-sm">technical.content</code>
```

**Typography hierarchy**:
- `text-4xl` (36px) — Page titles
- `text-2xl` (24px) — Section headings
- `text-lg` (18px) — Card titles
- `text-base` (16px) — Body text
- `text-sm` (14px) — Secondary text
- `text-xs` (12px) — Labels, captions

### Color & Theme

**ALWAYS support both light and dark modes**:

```html
<!-- ✅ CORRECT: Both modes styled -->
<div class="bg-white text-gray-900 dark:bg-gray-900 dark:text-white">
  <p class="text-gray-600 dark:text-gray-300">Secondary text</p>
  <div class="border border-gray-200 dark:border-gray-700">Content</div>
</div>

<!-- ❌ INCORRECT: Only light mode -->
<div class="bg-white text-gray-900">
  <p class="text-gray-600">Secondary text</p>
</div>
```

**Color strategy for AI platform**:
- **Primary actions**: `bg-primary-500 hover:bg-primary-600` (blue)
- **Success states**: `bg-green-500 text-white`
- **Warning states**: `bg-yellow-500 text-gray-900`
- **Error states**: `bg-red-500 text-white`
- **Neutral surfaces**: `bg-white dark:bg-gray-800`
- **Borders**: `border-gray-200 dark:border-gray-700`

### Motion & Animation

**Use Tailwind transitions** for micro-interactions:

```html
<!-- Hover states -->
<button class="
  bg-primary-500 text-white
  transition-colors duration-200
  hover:bg-primary-600
  focus-visible:ring-2 focus-visible:ring-primary-500
">
  Action
</button>

<!-- Loading states -->
<div class="animate-pulse">
  <div class="h-4 bg-gray-200 rounded-sm dark:bg-gray-700"></div>
</div>

<!-- Fade in -->
<div class="transition-opacity duration-300 opacity-0 data-[loaded]:opacity-100">
  Content
</div>
```

**Respect reduced motion**:
```html
<div class="transition-transform motion-reduce:transition-none">
  Animated content
</div>
```

### Layout Patterns

**Use Tailwind's layout utilities**:

```html
<!-- Responsive grid -->
<div class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
  <div class="rounded-sm bg-white p-6 shadow-sm dark:bg-gray-800">Card</div>
</div>

<!-- Flex with gap -->
<div class="flex items-center gap-3">
  <svg class="size-5 text-gray-500" />
  <span class="text-sm">Label</span>
</div>

<!-- Container with max-width -->
<div class="mx-auto max-w-7xl px-4 py-8">
  Content
</div>

<!-- Sticky header -->
<header class="sticky top-0 z-50 bg-white/95 backdrop-blur dark:bg-gray-900/95">
  Navigation
</header>
```

### Accessibility Requirements

**ALWAYS include** (see tailwind-accessibility.md for details):
- Visible focus states: `focus-visible:ring-2 focus-visible:ring-primary-500`
- ARIA labels for icon buttons: `<span class="sr-only">Close</span>`
- Proper color contrast (4.5:1 for text, 3:1 for UI)
- Semantic HTML: `<button>`, `<nav>`, `<main>`, `<article>`
- Form labels: `<label for="input-id">Label</label>`
- Error announcements: `<p role="alert">Error message</p>`



## Visual Enhancement Techniques

When appropriate for the aesthetic direction, add depth and interest:

### Subtle Backgrounds

```html
<!-- Gradient mesh (use sparingly) -->
<div class="bg-gradient-to-br from-primary-50 to-secondary-50 dark:from-gray-900 dark:to-gray-800">
  Content
</div>

<!-- Pattern backgrounds -->
<div class="bg-[url('/patterns/grid.svg')] bg-repeat opacity-5">
  Content
</div>
```

### Shadows & Depth

```html
<!-- Card with shadow -->
<div class="rounded-sm bg-white shadow-sm dark:bg-gray-800 dark:shadow-2xl dark:shadow-black/25">
  Card content
</div>

<!-- Elevated element -->
<div class="shadow-lg ring-1 ring-black/5 dark:ring-white/10">
  Elevated content
</div>
```

### Borders & Dividers

```html
<!-- Subtle borders -->
<div class="border border-gray-200 dark:border-gray-700">
  Content
</div>

<!-- Accent borders -->
<div class="border-l-4 border-primary-500">
  Highlighted content
</div>

<!-- Dividers -->
<div class="divide-y divide-gray-200 dark:divide-gray-700">
  <div>Item 1</div>
  <div>Item 2</div>
</div>
```

## Component Design Patterns

### Chat Interface

```html
<!-- Message list with proper spacing -->
<div class="flex flex-col gap-4 p-6">
  @for (message of messages(); track message.id) {
    <div class="flex gap-3" [class.flex-row-reverse]="message.role === 'user'">
      <div class="size-8 shrink-0 rounded-full bg-primary-500 text-white flex items-center justify-center">
        {{ message.role === 'user' ? 'U' : 'A' }}
      </div>
      <div class="flex-1 rounded-sm bg-white p-4 shadow-xs dark:bg-gray-800">
        <app-markdown [content]="message.content" />
      </div>
    </div>
  }
</div>
```

### Dashboard Cards

```html
<!-- Stat card -->
<div class="rounded-sm bg-white p-6 shadow-sm dark:bg-gray-800">
  <div class="flex items-center justify-between">
    <h3 class="text-sm font-medium text-gray-500 dark:text-gray-400">
      Total Requests
    </h3>
    <svg class="size-5 text-gray-400" />
  </div>
  <p class="mt-2 text-3xl font-semibold text-gray-900 dark:text-white">
    {{ totalRequests() | number }}
  </p>
  <p class="mt-1 text-sm text-gray-600 dark:text-gray-300">
    <span class="text-green-600 dark:text-green-400">+12%</span> from last month
  </p>
</div>
```

### Data Tables

```html
<!-- Responsive table -->
<div class="overflow-x-auto">
  <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
    <thead class="bg-gray-50 dark:bg-gray-800">
      <tr>
        <th class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
          Name
        </th>
      </tr>
    </thead>
    <tbody class="divide-y divide-gray-200 bg-white dark:divide-gray-700 dark:bg-gray-900">
      @for (item of items(); track item.id) {
        <tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
          <td class="whitespace-nowrap px-6 py-4 text-sm text-gray-900 dark:text-white">
            {{ item.name }}
          </td>
        </tr>
      }
    </tbody>
  </table>
</div>
```

### Loading States

```html
<!-- Skeleton loader -->
<div class="animate-pulse space-y-4">
  <div class="h-4 bg-gray-200 rounded-sm w-3/4 dark:bg-gray-700"></div>
  <div class="h-4 bg-gray-200 rounded-sm w-1/2 dark:bg-gray-700"></div>
</div>

<!-- Spinner -->
<div class="flex items-center justify-center p-8">
  <svg class="size-8 animate-spin text-primary-500" viewBox="0 0 24 24">
    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"/>
    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
  </svg>
</div>
```

## What to AVOID

**Never use these patterns**:
- ❌ Custom CSS classes when Tailwind utilities exist
- ❌ Inline styles (use Tailwind utilities)
- ❌ Missing dark mode variants
- ❌ Generic placeholder text ("Lorem ipsum")
- ❌ Inaccessible color combinations (check contrast)
- ❌ Icon buttons without accessible labels
- ❌ Forms without proper labels
- ❌ Missing focus states
- ❌ Animations without `motion-reduce` support
- ❌ Fixed pixel values (use Tailwind's spacing scale)

## Design Variation

Each component should feel intentionally designed:
- Vary between minimal and rich approaches based on context
- Chat interfaces: Clean, focused, readable
- Dashboards: Data-forward, organized, scannable
- Admin panels: Functional, efficient, clear
- Marketing pages: Bold, engaging, memorable

## Quality Checklist

Before considering a component complete:

**Functionality**:
- [ ] Component works with Angular signals and OnPush detection
- [ ] All interactive elements are keyboard accessible
- [ ] Loading and error states are handled
- [ ] Responsive on mobile, tablet, desktop

**Visual Design**:
- [ ] Both light and dark modes are styled
- [ ] Typography hierarchy is clear
- [ ] Spacing is consistent (using Tailwind scale)
- [ ] Colors meet WCAG AA contrast requirements
- [ ] Focus states are visible

**Code Quality**:
- [ ] Uses Tailwind utilities (minimal custom CSS)
- [ ] Follows Angular best practices (standalone, OnPush)
- [ ] Accessible markup (ARIA, semantic HTML)
- [ ] No console errors or warnings

## Creative Freedom Within Constraints

You have creative freedom to:
- Choose aesthetic direction (minimal, editorial, technical, etc.)
- Design unique layouts within responsive constraints
- Add subtle animations and micro-interactions
- Create distinctive visual hierarchies
- Make bold typographic choices

You must maintain:
- Accessibility standards (WCAG 2.1 AA)
- Light/dark mode support
- Mobile responsiveness
- Angular + Tailwind patterns
- Production-grade code quality

**Remember**: Distinctive design comes from intentional choices executed with precision, not from breaking fundamental usability principles.
