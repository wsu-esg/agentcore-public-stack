# Assistant Preview & Chat Container Refactoring Specification

## Overview

This specification describes the implementation of an assistant preview feature within the assistant form page, along with a refactoring of the chat UI into a reusable `ChatContainerComponent`. The goal is to allow users to test their assistants in real-time while editing, without persisting preview conversations to their session history.

---

## Table of Contents

1. [Feature Requirements](#feature-requirements)
2. [Architecture Overview](#architecture-overview)
3. [Backend Changes](#backend-changes)
4. [Frontend Changes](#frontend-changes)
5. [Component Specifications](#component-specifications)
6. [Service Specifications](#service-specifications)
7. [Shared Constants](#shared-constants)
8. [File Changes Summary](#file-changes-summary)

---

## Feature Requirements

### Functional Requirements

1. **Split Column Layout**: Assistant form page displays form inputs on the left (50%) and live preview on the right (50%)
2. **Hidden Sidenav**: Sidenav is hidden when entering the assistant form view, restored when leaving
3. **Live Preview Chat**: Users can send messages to test their assistant configuration
4. **Sessionless Preview**: Preview conversations use a special `preview-` prefixed session ID that the backend recognizes and skips persistence for
5. **Multi-turn Support**: Preview maintains conversation context within the same editing session
6. **Full Feature Parity**: Preview supports all chat features (streaming, tool use, tool results, citations, reasoning)

### Non-Functional Requirements

1. **No Global State Pollution**: Preview should not affect the main chat's state
2. **Instance-scoped Services**: Stream parsing and chat state should be isolated per preview instance
3. **Reusable Chat UI**: Extract chat UI into a reusable component for both session page and preview
4. **Maintainable Code**: Single source of truth for chat UI, no duplication

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     assistant-form.page                          │
├─────────────────────────────┬───────────────────────────────────┤
│     Form Inputs (50%)       │      Preview Panel (50%)          │
│                             │                                    │
│  - Name                     │  ┌─────────────────────────────┐  │
│  - Description              │  │   ChatContainerComponent    │  │
│  - Instructions             │  │   (embeddedMode: true)      │  │
│  - File Upload              │  │                             │  │
│                             │  │   - MessageListComponent    │  │
│                             │  │   - ChatInputComponent      │  │
│                             │  │                             │  │
│                             │  └─────────────────────────────┘  │
│                             │                                    │
│                             │  PreviewChatService (scoped)      │
│                             │  StreamParserService (scoped)     │
└─────────────────────────────┴───────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      session.page                                │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              ChatContainerComponent                         │ │
│  │              (fullPageMode: true)                           │ │
│  │                                                             │ │
│  │   - Topnav (fixed, sidenav-aware)                          │ │
│  │   - MessageListComponent                                    │ │
│  │   - ChatInputComponent (fixed footer, sidenav-aware)       │ │
│  │                                                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ChatRequestService (root)                                       │
│  StreamParserService (root)                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Backend Changes

### 1. Preview Session Detection

**File:** `backend/src/apis/inference_api/chat/routes.py`

Add a helper function to detect preview sessions:

```python
# Preview session prefix - sessions with this prefix skip persistence
PREVIEW_SESSION_PREFIX = "preview-"


def is_preview_session(session_id: str) -> bool:
    """Check if a session ID is a preview session (should skip persistence).

    Preview sessions are used for assistant testing in the form builder.
    They allow full agent functionality but don't save to user's conversation history.
    """
    return session_id.startswith(PREVIEW_SESSION_PREFIX)
```

### 2. Skip Persistence for Preview Sessions

Wrap persistence operations with preview checks:

```python
# In stream_conversational_message() - after emitting done event:
if is_preview_session(session_id):
    logger.info(f"🔍 Preview session {session_id} - skipping message persistence")
    return

# Continue with normal persistence...
```

```python
# In invocations endpoint - session state validation:
if not is_preview_session(input_data.session_id):
    # Check existing assistant, validate session state, etc.
else:
    logger.info(f"🔍 Preview session - skipping session state validation")
```

```python
# In invocations endpoint - assistant_id persistence:
if not is_preview_session(input_data.session_id):
    # Save assistant_id to session preferences
else:
    logger.info(f"🔍 Preview session - skipping assistant_id persistence")
```

### 3. Locations to Add Preview Checks

| Location | What to Skip |
|----------|-------------|
| `stream_conversational_message()` after done event | Message persistence to AgentCore Memory |
| Assistant validation block | Session state checks (existing assistant, message count) |
| Assistant preferences save | `store_session_metadata()` call |

---

## Frontend Changes

### Directory Structure

```
frontend/ai.client/src/app/
├── session/
│   ├── components/
│   │   └── chat-container/
│   │       ├── chat-container.component.ts    # NEW - Reusable chat UI
│   │       ├── chat-container.component.html  # NEW
│   │       └── chat-container.component.css   # NEW
│   ├── services/
│   │   └── chat/
│   │       └── stream-parser.service.ts       # MODIFY - Allow instance scoping
│   ├── session.page.ts                        # MODIFY - Use ChatContainerComponent
│   └── session.page.html                      # MODIFY - Simplified
├── assistants/
│   └── assistant-form/
│       ├── assistant-form.page.ts             # MODIFY - Split layout, hide sidenav
│       ├── assistant-form.page.html           # MODIFY - Two column layout
│       └── components/
│           └── assistant-preview.component.ts # NEW - Preview panel
├── services/
│   └── sidenav/
│       └── sidenav.service.ts                 # EXISTS - Already has hide()/show()
└── shared/
    └── constants/
        └── session.constants.ts               # NEW - Shared constants
```

---

## Component Specifications

### ChatContainerComponent

**Purpose:** Reusable chat UI that can be used in both full-page mode (session page) and embedded mode (assistant preview).

**File:** `session/components/chat-container/chat-container.component.ts`

```typescript
export interface ChatContainerConfig {
  /** Show the top navigation bar (full-page mode only) */
  showTopnav: boolean;
  /** Show the greeting/empty state */
  showEmptyState: boolean;
  /** Allow closing the assistant card */
  allowCloseAssistant: boolean;
  /** Show file attachment controls in chat input */
  showFileControls: boolean;
  /** Custom greeting message (overrides default) */
  customGreeting?: string;
  /** Enable embedded mode (flex layout, no fixed positioning) */
  embeddedMode: boolean;
  /** Enable full-page mode (fixed positioning with sidenav awareness) */
  fullPageMode: boolean;
}

@Component({
  selector: 'app-chat-container',
  standalone: true,
  imports: [
    MessageListComponent,
    ChatInputComponent,
    AnimatedTextComponent,
    ParagraphSkeletonComponent,
    Topnav,
    NgIcon
  ],
  providers: [provideIcons({ heroXMark })],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './chat-container.component.html',
  styleUrl: './chat-container.component.css'
})
export class ChatContainerComponent {
  // Inject sidenav service for full-page mode positioning
  protected sidenavService = inject(SidenavService);

  // Required inputs
  messages = input.required<Message[]>();
  sessionId = input<string | null>(null);

  // Optional inputs
  assistant = input<Assistant | null>(null);
  assistantError = input<string | null>(null);
  isChatLoading = input<boolean>(false);
  isLoadingSession = input<boolean>(false);
  streamingMessageId = input<string | null>(null);
  greetingMessage = input<string>('How can I help you today?');

  // Configuration with defaults
  config = input<Partial<ChatContainerConfig>>({});

  protected readonly resolvedConfig = computed<ChatContainerConfig>(() => ({
    showTopnav: false,
    showEmptyState: true,
    allowCloseAssistant: true,
    showFileControls: true,
    embeddedMode: false,
    fullPageMode: false,
    ...this.config()
  }));

  // Output events
  messageSubmitted = output<{ content: string; timestamp: Date; fileUploadIds?: string[] }>();
  messageCancelled = output<void>();
  fileAttached = output<File>();
  settingsToggled = output<void>();
  assistantClosed = output<void>();

  // Computed signals
  protected readonly hasMessages = computed(() => this.messages().length > 0);
  protected readonly showSkeleton = computed(() => this.isLoadingSession() && !this.hasMessages());
  protected readonly canCloseAssistant = computed(() =>
    this.resolvedConfig().allowCloseAssistant && !this.hasMessages() && !!this.assistant()
  );
  protected readonly isSidenavCollapsed = computed(() => this.sidenavService.isCollapsed());
}
```

**CSS Classes:**

| Class | Mode | Description |
|-------|------|-------------|
| `.embedded` | Embedded | Flex layout, relative positioning, border separators |
| `.full-page` | Full-page | Fixed positioning for topnav/footer |
| `.sidenav-expanded` | Full-page | Applies `left: 18rem` offset on lg screens |

**CSS Structure:**

```css
/* Use media query for sidenav-aware positioning */
@media (min-width: 1024px) {
  .chat-input-footer.full-page.sidenav-expanded,
  .chat-container-empty.full-page.sidenav-expanded,
  .chat-topnav-wrapper.sidenav-expanded {
    left: 18rem; /* 72 in Tailwind = 18rem */
  }
}

.chat-topnav-wrapper {
  @apply fixed top-0 left-0 right-0 z-40 transition-[left] duration-300;
}

.chat-input-footer.full-page {
  @apply pb-4 fixed bottom-0 left-0 right-0 transition-[left] duration-300;
}

.chat-container-empty.full-page {
  @apply fixed inset-0 transition-[left] duration-300;
}
```

### AssistantPreviewComponent

**Purpose:** Wrapper component for the preview panel that provides the preview-specific chat service.

**File:** `assistants/assistant-form/components/assistant-preview.component.ts`

```typescript
@Component({
  selector: 'app-assistant-preview',
  standalone: true,
  imports: [ChatContainerComponent, NgIcon],
  providers: [
    PreviewChatService,      // Component-scoped
    StreamParserService,     // Component-scoped instance
    provideIcons({ heroSparkles })
  ],
  template: `
    @if (!assistantId()) {
      <!-- Placeholder when no assistant saved yet -->
      <div class="h-full flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div class="text-center p-8">
          <ng-icon name="heroSparkles" class="size-12 text-gray-400 mx-auto mb-4" />
          <p class="text-gray-500 dark:text-gray-400">
            Save your assistant to enable the chat preview
          </p>
        </div>
      </div>
    } @else {
      <app-chat-container
        [messages]="previewChatService.messages()"
        [sessionId]="null"
        [assistant]="assistantObject()"
        [isChatLoading]="previewChatService.isLoading()"
        [streamingMessageId]="previewChatService.streamingMessageId()"
        [greetingMessage]="greetingMessage()"
        [config]="chatConfig"
        (messageSubmitted)="onMessageSubmitted($event)"
        (messageCancelled)="onMessageCancelled()"
      />
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class AssistantPreviewComponent implements OnDestroy {
  protected previewChatService = inject(PreviewChatService);

  // Inputs from parent form
  assistantId = input<string | null>(null);
  name = input<string>('');
  description = input<string>('');
  instructions = input<string>('');

  readonly chatConfig: Partial<ChatContainerConfig> = {
    embeddedMode: true,
    allowCloseAssistant: false,
    showEmptyState: true,
    showTopnav: false,
    showFileControls: false
  };

  // Build assistant object for display
  protected readonly assistantObject = computed(() => ({
    id: this.assistantId() || '',
    name: this.name() || 'New Assistant',
    description: this.description() || '',
    instructions: this.instructions() || '',
    // Required fields with defaults
    ownerId: '',
    ownerName: '',
    tags: [],
    usageCount: 0,
    status: 'active' as const,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  }));

  protected readonly greetingMessage = computed(() =>
    `Chat with ${this.name() || 'your assistant'}`
  );

  onMessageSubmitted(event: { content: string }) {
    const id = this.assistantId();
    if (id) {
      this.previewChatService.sendMessage(event.content, id);
    }
  }

  onMessageCancelled() {
    this.previewChatService.cancelRequest();
  }

  ngOnDestroy() {
    this.previewChatService.reset();
  }
}
```

---

## Service Specifications

### PreviewChatService

**Purpose:** Component-scoped service for managing preview chat state and API communication.

**File:** `assistants/assistant-form/services/preview-chat.service.ts`

**Key Design Decisions:**
1. **Component-scoped** - Provided at component level, not root
2. **Own StreamParserService** - Doesn't share with main chat
3. **No global state mutation** - Does NOT modify ChatStateService

```typescript
import { PREVIEW_SESSION_PREFIX } from '../../../shared/constants/session.constants';

@Injectable() // NOT providedIn: 'root' - component scoped
export class PreviewChatService {
  private authService = inject(AuthService);
  private modelService = inject(ModelService);
  private toolService = inject(ToolService);
  private streamParser = inject(StreamParserService); // Will be component-scoped instance

  // Local state
  private messagesSignal = signal<Message[]>([]);
  private isLoadingSignal = signal(false);
  private streamingMessageIdSignal = signal<string | null>(null);
  private abortController: AbortController | null = null;
  private previewSessionId = `${PREVIEW_SESSION_PREFIX}${uuidv4()}`;
  private messageCount = 0;

  // Public readonly signals
  readonly messages = this.messagesSignal.asReadonly();
  readonly isLoading = this.isLoadingSignal.asReadonly();
  readonly streamingMessageId = this.streamingMessageIdSignal.asReadonly();

  async sendMessage(content: string, assistantId: string): Promise<void> {
    if (this.isLoadingSignal() || !content.trim() || !assistantId) return;

    // Create and add user message
    const userMessage = this.createUserMessage(content);
    this.messagesSignal.update(msgs => [...msgs, userMessage]);
    this.messageCount++;

    // Start streaming
    this.isLoadingSignal.set(true);
    this.abortController = new AbortController();
    this.streamParser.reset(this.previewSessionId, this.messageCount);

    try {
      await this.streamChatRequest(content, assistantId);
      // Sync messages from parser
      this.syncMessagesFromParser();
    } catch (error) {
      if ((error as Error).name !== 'AbortError') {
        this.addErrorMessage();
      }
    } finally {
      this.isLoadingSignal.set(false);
      this.streamingMessageIdSignal.set(null);
      this.abortController = null;
    }
  }

  cancelRequest(): void {
    this.abortController?.abort();
    this.isLoadingSignal.set(false);
    this.streamingMessageIdSignal.set(null);
  }

  clearMessages(): void {
    this.messagesSignal.set([]);
    this.messageCount = 0;
    this.streamParser.reset();
  }

  reset(): void {
    this.cancelRequest();
    this.clearMessages();
    this.previewSessionId = `${PREVIEW_SESSION_PREFIX}${uuidv4()}`;
  }

  private async streamChatRequest(message: string, assistantId: string): Promise<void> {
    const token = await this.getBearerToken();
    const enabledTools = this.toolService.getEnabledToolIds();

    const requestObject: Record<string, unknown> = {
      message,
      session_id: this.previewSessionId,
      assistant_id: assistantId,
      enabled_tools: enabledTools
    };

    // Only include model if not default
    const selectedModel = this.modelService.getSelectedModel();
    if (!this.modelService.isUsingDefaultModel() && selectedModel) {
      requestObject['model_id'] = selectedModel.modelId;
      requestObject['provider'] = selectedModel.provider;
    }

    await fetchEventSource(`${environment.inferenceApiUrl}/invocations?qualifier=DEFAULT`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        'Accept': 'text/event-stream'
      },
      body: JSON.stringify(requestObject),
      signal: this.abortController?.signal,
      onmessage: (msg) => {
        if (msg.data) {
          try {
            const data = JSON.parse(msg.data);
            this.streamParser.parseEventSourceMessage(msg.event, data);
            // Update streaming message ID
            this.streamingMessageIdSignal.set(this.streamParser.streamingMessageId());
            // Sync messages reactively
            this.syncMessagesFromParser();
          } catch { /* ignore parse errors */ }
        }
      },
      onerror: (err) => { throw err; }
    });
  }

  private syncMessagesFromParser(): void {
    const parserMessages = this.streamParser.allMessages();
    const assistantMessages = parserMessages.filter(m => m.role === 'assistant');
    const userMessages = this.messagesSignal().filter(m => m.role === 'user');
    this.messagesSignal.set([...userMessages, ...assistantMessages]);
  }
}
```

### ChatInputComponent Modification

**Purpose:** Accept loading state as input instead of reading from global ChatStateService.

**File:** `session/components/chat-input/chat-input.component.ts`

```typescript
@Component({...})
export class ChatInputComponent {
  // NEW: Accept loading state as input
  isChatLoading = input<boolean | undefined>(undefined);

  // Existing injection for fallback
  private chatState = inject(ChatStateService);

  // Computed that prefers input over global state
  protected readonly isLoading = computed(() =>
    this.isChatLoading() ?? this.chatState.isChatLoading()
  );
}
```

Then in template, use `isLoading()` instead of `chatState.isChatLoading()`.

### ChatContainerComponent - Pass Loading State

```html
<app-chat-input
  [sessionId]="sessionId()"
  [isChatLoading]="isChatLoading()"
  (messageSubmitted)="onMessageSubmitted($event)"
  ...
/>
```

---

## Shared Constants

**File:** `shared/constants/session.constants.ts`

```typescript
/**
 * Prefix for preview session IDs.
 * Sessions with this prefix are recognized by the backend and skip persistence.
 */
export const PREVIEW_SESSION_PREFIX = 'preview-';

/**
 * Check if a session ID is a preview session.
 */
export function isPreviewSession(sessionId: string): boolean {
  return sessionId.startsWith(PREVIEW_SESSION_PREFIX);
}
```

---

## File Changes Summary

### New Files

| File | Purpose |
|------|---------|
| `session/components/chat-container/chat-container.component.ts` | Reusable chat UI component |
| `session/components/chat-container/chat-container.component.html` | Chat container template |
| `session/components/chat-container/chat-container.component.css` | Chat container styles |
| `assistants/assistant-form/components/assistant-preview.component.ts` | Preview panel component |
| `assistants/assistant-form/services/preview-chat.service.ts` | Preview-specific chat service |
| `shared/constants/session.constants.ts` | Shared constants for session handling |

### Modified Files

| File | Changes |
|------|---------|
| `session/session.page.ts` | Use ChatContainerComponent, remove duplicated logic |
| `session/session.page.html` | Replace duplicated template with ChatContainerComponent |
| `session/components/chat-input/chat-input.component.ts` | Add `isChatLoading` input |
| `assistants/assistant-form/assistant-form.page.ts` | Add sidenav hide/show, split layout |
| `assistants/assistant-form/assistant-form.page.html` | Two-column layout with preview |
| `backend/.../chat/routes.py` | Add `is_preview_session()` helper, skip persistence |

### Files to Export

Add to barrel files:
- `session/components/chat-container/index.ts`
- `shared/constants/index.ts`

---

## Testing Checklist

### Backend
- [ ] Preview session (`preview-*`) skips message persistence
- [ ] Preview session skips session state validation
- [ ] Preview session skips assistant_id preference storage
- [ ] Regular sessions still persist correctly
- [ ] Multi-turn conversations work in preview (agent has context)

### Frontend - Preview
- [ ] Preview appears when assistant is saved
- [ ] Placeholder shown when assistant not yet saved
- [ ] Messages stream correctly with tool use
- [ ] Tool results display properly
- [ ] Citations display properly
- [ ] Loading state shows/hides correctly
- [ ] Cancel button works
- [ ] Multi-turn conversation maintains context
- [ ] Clearing messages works
- [ ] Leaving and returning to form resets preview

### Frontend - Session Page
- [ ] Session page renders correctly with ChatContainerComponent
- [ ] Topnav positioning correct with sidenav open/closed
- [ ] Chat input positioning correct with sidenav open/closed
- [ ] Empty state displays correctly
- [ ] Skeleton loading displays correctly
- [ ] All existing functionality preserved

### Frontend - Isolation
- [ ] Preview chat doesn't affect main chat loading state
- [ ] Main chat doesn't affect preview state
- [ ] Running both simultaneously works correctly

---

## Migration Notes

1. **Do not incrementally migrate** - Replace all at once to avoid partial states
2. **Test sidenav transitions** - Ensure smooth animation when toggling
3. **Verify tool rendering** - Preview must handle all tool types the main chat does
4. **Check mobile responsiveness** - Preview panel should handle narrow widths gracefully

---

## Future Improvements (Out of Scope)

1. **NoOpSessionManager** - For completely stateless preview (no AgentCore Memory writes at all)
2. **Preview history persistence** - Save/restore preview conversations per assistant
3. **Side-by-side comparison** - Compare different assistant configurations
4. **Preview in modal** - Alternative to split layout for smaller screens
