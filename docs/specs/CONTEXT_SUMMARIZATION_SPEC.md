# Context Summarization Implementation Spec

## Overview

Implement intelligent conversation context management using Strands Agents' `SummarizingConversationManager`. This feature automatically summarizes older messages when context limits are approached, preserving essential information while reducing token usage and costs.

## Goals

1. **Automatic Context Compression**: Reduce context size when token limits are reached
2. **Cost Optimization**: Use Nova Micro as a dedicated, cost-effective summarization model
3. **User Transparency**: Notify users when summarization occurs via SSE events and UI indicators
4. **Configurability**: Allow administrators to tune summarization behavior via environment variables

## Technical Design

### 1. Backend Implementation

#### 1.1 Environment Variables

Add the following environment variables to configure summarization:

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SUMMARIZATION_ENABLED` | bool | `true` | Feature toggle for context summarization |
| `SUMMARIZATION_MODEL_ID` | str | `us.amazon.nova-micro-v1:0` | Model ID for the summarization agent |
| `SUMMARIZATION_SUMMARY_RATIO` | float | `0.3` | Percentage of messages to summarize (0.1-0.8) |
| `SUMMARIZATION_PRESERVE_RECENT` | int | `10` | Minimum recent messages to always preserve |

#### 1.2 Summarization Agent Configuration

**File:** `backend/src/agents/main_agent/core/summarization_config.py` (new)

```python
from dataclasses import dataclass
from typing import Optional
import os

@dataclass
class SummarizationConfig:
    """Configuration for context summarization"""
    enabled: bool = True
    model_id: str = "us.amazon.nova-micro-v1:0"
    summary_ratio: float = 0.3
    preserve_recent_messages: int = 10

    @classmethod
    def from_env(cls) -> "SummarizationConfig":
        """Load configuration from environment variables"""
        return cls(
            enabled=os.getenv("SUMMARIZATION_ENABLED", "true").lower() == "true",
            model_id=os.getenv("SUMMARIZATION_MODEL_ID", "us.amazon.nova-micro-v1:0"),
            summary_ratio=float(os.getenv("SUMMARIZATION_SUMMARY_RATIO", "0.3")),
            preserve_recent_messages=int(os.getenv("SUMMARIZATION_PRESERVE_RECENT", "10"))
        )
```

#### 1.3 Agent Factory Integration

**File:** `backend/src/agents/main_agent/core/agent_factory.py`

Modify `create_agent()` to use `SummarizingConversationManager`:

```python
from strands.agent.conversation_manager import SummarizingConversationManager
from strands import Agent
from .summarization_config import SummarizationConfig

def create_agent(...) -> Agent:
    summarization_config = SummarizationConfig.from_env()

    conversation_manager = None
    if summarization_config.enabled:
        # Create dedicated summarization agent with Nova Micro
        summarization_agent = Agent(
            model_id=summarization_config.model_id,
            # Minimal config - no tools needed for summarization
        )

        conversation_manager = SummarizingConversationManager(
            summary_ratio=summarization_config.summary_ratio,
            preserve_recent_messages=summarization_config.preserve_recent_messages,
            summarization_agent=summarization_agent
        )

    return Agent(
        model_id=model_config.model_id,
        conversation_manager=conversation_manager,
        # ... existing config
    )
```

#### 1.4 Summarization Event Detection

The `SummarizingConversationManager` modifies the message history when summarization occurs. We need to detect this and emit events.

**Approach:** Hook into the conversation manager or compare message counts before/after agent invocation.

**File:** `backend/src/agents/main_agent/streaming/stream_coordinator.py`

Add summarization detection logic:

```python
async def detect_summarization(
    messages_before: list,
    messages_after: list,
    session_id: str,
    user_id: str
) -> Optional[SummarizationEvent]:
    """
    Detect if summarization occurred by comparing message lists.

    Returns SummarizationEvent if summarization was detected, None otherwise.
    """
    # Check for summary message (first assistant message with summary content)
    # SummarizingConversationManager replaces old messages with a summary

    if len(messages_after) < len(messages_before):
        # Messages were compressed
        tokens_before = estimate_tokens(messages_before)
        tokens_after = estimate_tokens(messages_after)

        # Find the summary text (typically first message after summarization)
        summary_text = extract_summary_text(messages_after)

        return SummarizationEvent(
            session_id=session_id,
            user_id=user_id,
            messages_before_count=len(messages_before),
            messages_after_count=len(messages_after),
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            tokens_removed=tokens_before - tokens_after,
            summary_text=summary_text,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    return None
```

#### 1.4 SSE Event Model

**File:** `backend/src/apis/shared/summarization.py` (new)

```python
from pydantic import BaseModel, Field
from typing import Optional
import json

class ContextSummarizedEvent(BaseModel):
    """SSE event emitted when context summarization occurs"""
    type: str = "context_summarized"
    session_id: str = Field(..., alias="sessionId")
    tokens_before: int = Field(..., alias="tokensBefore", description="Token count before summarization")
    tokens_after: int = Field(..., alias="tokensAfter", description="Token count after summarization")
    tokens_removed: int = Field(..., alias="tokensRemoved", description="Tokens removed by summarization")
    messages_summarized: int = Field(..., alias="messagesSummarized", description="Number of messages summarized")
    context_compression_ratio: float = Field(..., alias="contextCompressionRatio", description="Compression ratio (0-1)")
    message: str = Field(..., description="User-friendly message")

    def to_sse_format(self) -> str:
        """Format as Server-Sent Event"""
        return f"event: context_summarized\ndata: {json.dumps(self.model_dump(by_alias=True))}\n\n"

    @classmethod
    def create(
        cls,
        session_id: str,
        tokens_before: int,
        tokens_after: int,
        messages_summarized: int
    ) -> "ContextSummarizedEvent":
        """Factory method with computed fields"""
        tokens_removed = tokens_before - tokens_after
        compression_ratio = tokens_removed / tokens_before if tokens_before > 0 else 0

        return cls(
            session_id=session_id,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            tokens_removed=tokens_removed,
            messages_summarized=messages_summarized,
            context_compression_ratio=compression_ratio,
            message=f"Context optimized: {tokens_removed:,} tokens compressed"
        )
```

#### 1.5 Chat Routes Integration

**File:** `backend/src/apis/app_api/chat/routes.py`

Emit the summarization event during streaming:

```python
# After agent response, check for summarization
summarization_event = await detect_summarization(
    messages_before=messages_snapshot,
    messages_after=agent.messages,
    session_id=session_id,
    user_id=user_id
)

if summarization_event:
    # Emit SSE event
    yield summarization_event.to_sse_format()
```

### 2. Frontend Implementation

#### 2.1 SSE Event Handler

**File:** `frontend/ai.client/src/app/session/services/chat/stream-parser.service.ts`

Add handler for the new event type:

```typescript
// Add to handleEvent switch statement
case 'context_summarized':
  this.handleContextSummarized(data);
  break;

// Add handler method
private handleContextSummarized(data: unknown): void {
  if (!data || typeof data !== 'object') return;

  const event = data as Partial<ContextSummarizedEvent>;

  if (event.type !== 'context_summarized' ||
      typeof event.tokensBefore !== 'number' ||
      typeof event.tokensRemoved !== 'number') {
    console.warn('Invalid context_summarized event:', data);
    return;
  }

  this.contextSummarizationService.setContextSummarized(event as ContextSummarizedEvent);
}
```

#### 2.2 Context Summarization Service

**File:** `frontend/ai.client/src/app/services/summarization/context-summarization.service.ts` (new)

```typescript
import { Injectable, signal, computed } from '@angular/core';

export interface ContextSummarizedEvent {
  type: 'context_summarized';
  sessionId: string;
  tokensBefore: number;
  tokensAfter: number;
  tokensRemoved: number;
  messagesSummarized: number;
  contextCompressionRatio: number;
  message: string;
}

@Injectable({ providedIn: 'root' })
export class ContextSummarizationService {
  // Signal for current summarization event
  private contextSummarizedSignal = signal<ContextSummarizedEvent | null>(null);

  // Signal for sessions that have been summarized (persists across messages)
  private summarizedSessionsSignal = signal<Set<string>>(new Set());

  // Public readonly signals
  readonly contextSummarized = this.contextSummarizedSignal.asReadonly();
  readonly summarizedSessions = this.summarizedSessionsSignal.asReadonly();

  // Computed: Should show the inline notification banner
  readonly showNotificationBanner = computed(() => {
    return this.contextSummarizedSignal() !== null;
  });

  // Computed: Check if a specific session has been summarized
  readonly isSessionSummarized = (sessionId: string) => {
    return this.summarizedSessionsSignal().has(sessionId);
  };

  // Computed: Formatted message for display
  readonly displayMessage = computed(() => {
    const event = this.contextSummarizedSignal();
    if (!event) return '';

    const tokensK = Math.round(event.tokensRemoved / 1000);
    const percent = Math.round(event.contextCompressionRatio * 100);

    if (tokensK >= 1) {
      return `Context optimized: ~${tokensK}K tokens compressed (${percent}% reduction)`;
    }
    return `Context optimized: ${event.tokensRemoved.toLocaleString()} tokens compressed`;
  });

  /**
   * Set a new context summarized event
   */
  setContextSummarized(event: ContextSummarizedEvent): void {
    this.contextSummarizedSignal.set(event);

    // Track that this session has been summarized
    this.summarizedSessionsSignal.update(sessions => {
      const updated = new Set(sessions);
      updated.add(event.sessionId);
      return updated;
    });
  }

  /**
   * Dismiss the notification banner (but keep session marked as summarized)
   */
  dismissBanner(): void {
    this.contextSummarizedSignal.set(null);
  }

  /**
   * Clear summarization state for a session (e.g., when starting new session)
   */
  clearSession(sessionId: string): void {
    this.summarizedSessionsSignal.update(sessions => {
      const updated = new Set(sessions);
      updated.delete(sessionId);
      return updated;
    });

    // Also clear banner if it's for this session
    if (this.contextSummarizedSignal()?.sessionId === sessionId) {
      this.contextSummarizedSignal.set(null);
    }
  }
}
```

#### 2.3 UI Component - Inline Banner

**File:** `frontend/ai.client/src/app/components/context-summarization-banner/context-summarization-banner.component.ts` (new)

Following the pattern from `quota-warning-banner.component.ts`:

```typescript
import { Component, inject, ChangeDetectionStrategy } from '@angular/core';
import { NgIconComponent, provideIcons } from '@ng-icon/core';
import { heroSparkles, heroXMark } from '@ng-icons/heroicons/outline';
import { ContextSummarizationService } from '../../services/summarization/context-summarization.service';

@Component({
  selector: 'app-context-summarization-banner',
  standalone: true,
  imports: [NgIconComponent],
  viewProviders: [provideIcons({ heroSparkles, heroXMark })],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (service.showNotificationBanner()) {
      <div
        class="inline-flex items-center gap-2 px-3 py-2 text-xs rounded-lg border
               border-blue-200 bg-blue-50 text-blue-700
               dark:border-blue-800 dark:bg-blue-900/30 dark:text-blue-300
               animate-fade-in shadow-sm"
        role="status"
        aria-live="polite"
      >
        <ng-icon name="heroSparkles" class="size-4 shrink-0" />
        <span class="font-medium">{{ service.displayMessage() }}</span>
        <button
          (click)="dismiss($event)"
          class="ml-1 p-0.5 rounded hover:bg-blue-100 dark:hover:bg-blue-800/50
                 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
          aria-label="Dismiss notification"
        >
          <ng-icon name="heroXMark" class="size-3" />
        </button>
      </div>
    }
  `
})
export class ContextSummarizationBannerComponent {
  protected service = inject(ContextSummarizationService);

  dismiss(event: Event): void {
    event.stopPropagation();
    this.service.dismissBanner();
  }
}
```

#### 2.4 Session Badge Indicator

Add a small indicator to sessions that have been summarized.

**File:** Modify session list item component

```typescript
// In session list item template
@if (contextSummarizationService.isSessionSummarized(session.sessionId)) {
  <span
    class="inline-flex items-center text-blue-500 dark:text-blue-400"
    [appTooltip]="'Context has been summarized'"
    appTooltipPosition="top"
  >
    <ng-icon name="heroSparkles" class="size-3" />
  </span>
}
```

#### 2.5 Types Definition

**File:** `frontend/ai.client/src/app/session/services/chat/types.ts`

Add the event type:

```typescript
export interface ContextSummarizedEvent {
  type: 'context_summarized';
  sessionId: string;
  tokensBefore: number;
  tokensAfter: number;
  tokensRemoved: number;
  messagesSummarized: number;
  contextCompressionRatio: number;
  message: string;
}
```

### 3. Infrastructure Changes

#### 3.1 CDK Configuration

**File:** `infrastructure/lib/app-api-stack.ts`

Add environment variables to the ECS task definition:

```typescript
// In container definition environment
SUMMARIZATION_ENABLED: config.appApi.summarizationEnabled?.toString() ?? 'true',
SUMMARIZATION_MODEL_ID: config.appApi.summarizationModelId ?? 'us.amazon.nova-micro-v1:0',
SUMMARIZATION_SUMMARY_RATIO: config.appApi.summarizationSummaryRatio?.toString() ?? '0.3',
SUMMARIZATION_PRESERVE_RECENT: config.appApi.summarizationPreserveRecent?.toString() ?? '10',
```

#### 3.2 Config Schema

**File:** `infrastructure/lib/config.ts`

Add configuration options:

```typescript
interface AppApiConfig {
  // ... existing fields
  summarizationEnabled?: boolean;
  summarizationModelId?: string;
  summarizationSummaryRatio?: number;
  summarizationPreserveRecent?: number;
}
```

## Data Flow

```
User sends message
    │
    ▼
Agent processes request
    │
    ▼
SummarizingConversationManager checks context size
    │
    ├─ Context OK ─────────────────────────────────► Continue normally
    │
    └─ Context exceeds limit
           │
           ▼
       Summarization Agent (Nova Micro)
       creates summary of old messages
           │
           ▼
       Old messages replaced with summary
           │
           ▼
       detect_summarization() compares before/after
           │
           ▼
       Emit SSE event: context_summarized
           │
           ▼
       Frontend: ContextSummarizationService
           └─► Show inline banner
           └─► Mark session as summarized
```

## SSE Event Format

```json
{
  "type": "context_summarized",
  "sessionId": "abc123",
  "tokensBefore": 45000,
  "tokensAfter": 32000,
  "tokensRemoved": 13000,
  "messagesSummarized": 8,
  "contextCompressionRatio": 0.29,
  "message": "Context optimized: 13,000 tokens compressed"
}
```

## Testing Strategy

### Unit Tests

1. `SummarizationConfig` - Environment variable parsing
2. `ContextSummarizedEvent` - SSE formatting, factory method
3. `detect_summarization()` - Summarization detection logic
4. `ContextSummarizationService` - Signal state management

### Integration Tests

1. End-to-end summarization flow with mock agent
2. SSE event emission and parsing
3. UI banner display and dismissal

### Manual Testing

1. Start a long conversation that exceeds context limits
2. Verify summarization event appears in SSE stream
3. Verify UI banner displays with correct message
4. Verify session shows summarization indicator

## Rollout Plan

1. **Phase 1**: Backend implementation with feature flag disabled
   - Add environment variables
   - Implement summarization config
   - Add SSE event model

2. **Phase 2**: Frontend implementation
   - Add SSE event handler
   - Create service and components
   - Add session indicators

3. **Phase 3**: Integration and testing
   - End-to-end testing
   - Performance validation
   - Cost analysis with Nova Micro

4. **Phase 4**: Gradual rollout
   - Enable for internal users first
   - Monitor summarization frequency and costs
   - Full rollout with `SUMMARIZATION_ENABLED=true`

## Success Metrics

1. **Context Compression**: Average tokens removed per summarization event
2. **Cost Savings**: Reduction in overall token costs from context compression
3. **Summarization Quality**: User feedback on conversation coherence post-summarization
4. **System Reliability**: Error rate for summarization operations

## Open Questions

1. Should there be a manual trigger option for users to request summarization?
2. What should happen if the summarization agent fails? (Current: fail gracefully, continue without summarization)

## Future Enhancements

1. **Audit Storage**: If needed for debugging or compliance, add DynamoDB persistence for summarization events with schema `SUM#{timestamp}#{session_id}`

## References

- [Strands Agents - Conversation Management](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/conversation-management/)
- [Strands Agents - Agent API Reference](https://strandsagents.com/latest/documentation/docs/api-reference/agent/)
- [AWS Nova Micro Pricing](https://aws.amazon.com/bedrock/pricing/)
