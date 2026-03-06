"""
Session Manager with Context Compaction for AgentCore Memory

This session manager provides:
1. Message count tracking (avoids eventual consistency issues with AgentCore Memory)
2. Proper hook registration (ensures our callbacks are used, not the base manager's)
3. Session cancellation support
4. Automatic context window compaction (truncation + checkpointing)

Compaction Strategy (two-feature approach):
- Stage 1: Tool content truncation - Applied every turn, reduces verbose tool I/O
- Stage 2: Checkpoint + Summary - Triggered when token threshold exceeded

Based on: https://medium.com/@tonypeng_30327/part-2-building-agent-memory-system-bedrock-agentcore-context-compaction-82917f4c2ba0
"""

import copy
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, TYPE_CHECKING

from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig

from .compaction_models import CompactionState, CompactionConfig

if TYPE_CHECKING:
    from strands.agent.agent import Agent

logger = logging.getLogger(__name__)


class TurnBasedSessionManager:
    """
    Session manager with built-in context compaction for AgentCore Memory.

    Features:
    - Message count tracking (initialized once at startup to avoid eventual consistency)
    - Proper hook registration (intercepts MessageAddedEvent to track count)
    - Session cancellation support
    - Two-feature compaction:
      1. Tool content truncation (every turn)
      2. Checkpoint + summary (when token threshold exceeded)

    The compaction state is stored as a nested attribute in the DynamoDB session
    record, not as a separate item. This ensures atomic updates and simplifies
    the storage layer.
    """

    # Class-level DynamoDB table reference for compaction state
    # Uses DYNAMODB_SESSIONS_METADATA_TABLE_NAME (same as session metadata)
    _dynamodb_table = None
    _dynamodb_table_name: Optional[str] = None

    def __init__(
        self,
        agentcore_memory_config: AgentCoreMemoryConfig,
        region_name: str = "us-west-2",
        compaction_config: Optional[CompactionConfig] = None,
        user_id: Optional[str] = None,
        summarization_strategy_id: Optional[str] = None,
    ):
        """
        Initialize session manager with optional compaction.

        Args:
            agentcore_memory_config: AgentCore Memory configuration
            region_name: AWS region
            compaction_config: Compaction configuration (None = disabled)
            user_id: User ID for DynamoDB session lookup
            summarization_strategy_id: Strategy ID for LTM summary retrieval
        """
        self.base_manager = AgentCoreMemorySessionManager(
            agentcore_memory_config=agentcore_memory_config,
            region_name=region_name
        )

        self.config = agentcore_memory_config
        self.region_name = region_name
        self.user_id = user_id
        self.summarization_strategy_id = summarization_strategy_id

        # Compaction config (None means disabled)
        self.compaction_config = compaction_config

        # Compaction state (loaded during initialize)
        self.compaction_state: Optional[CompactionState] = None

        # Cached data for checkpoint calculation
        self._valid_cutoff_indices: List[int] = []
        self._all_messages_for_summary: List[Dict] = []
        self._total_message_count_at_init: int = 0

        # Session control
        self.cancelled = False

        # Message count tracking
        self.message_count: int = self._initialize_message_count()

        # Log initialization
        if compaction_config and compaction_config.enabled:
            logger.info(
                f"✅ TurnBasedSessionManager initialized with compaction "
                f"(threshold={compaction_config.token_threshold:,}, "
                f"protected_turns={compaction_config.protected_turns}, "
                f"initial_message_count={self.message_count})"
            )
        else:
            logger.info(
                f"✅ TurnBasedSessionManager initialized "
                f"(compaction disabled, initial_message_count={self.message_count})"
            )

    def _get_dynamodb_table(self):
        """
        Lazy initialization of DynamoDB table for compaction state.

        Uses DYNAMODB_SESSIONS_METADATA_TABLE_NAME - the same table that stores
        session metadata (title, preferences, etc). Compaction state is stored
        as a nested 'compaction' attribute on the session record.
        """
        if TurnBasedSessionManager._dynamodb_table is None:
            table_name = os.environ.get('DYNAMODB_SESSIONS_METADATA_TABLE_NAME')
            if not table_name:
                logger.warning("DYNAMODB_SESSIONS_METADATA_TABLE_NAME not configured, compaction state will not persist")
                return None

            import boto3
            TurnBasedSessionManager._dynamodb_table_name = table_name
            dynamodb = boto3.resource('dynamodb', region_name=self.region_name)
            TurnBasedSessionManager._dynamodb_table = dynamodb.Table(table_name)
            logger.debug(f"Initialized DynamoDB table for compaction: {table_name}")
        return TurnBasedSessionManager._dynamodb_table

    def _get_session_via_gsi(self, table) -> Optional[Dict]:
        """
        Look up session record using GSI (SessionLookupIndex).

        With the SK pattern S#ACTIVE#{last_message_at}#{session_id}, we can't
        use get_item directly. The GSI allows lookup by session_id alone.

        Returns:
            Session item dict including PK/SK if found, None otherwise
        """
        try:
            from boto3.dynamodb.conditions import Key

            response = table.query(
                IndexName='SessionLookupIndex',
                KeyConditionExpression=(
                    Key('GSI_PK').eq(f'SESSION#{self.config.session_id}') &
                    Key('GSI_SK').eq('META')
                )
            )

            items = response.get('Items', [])
            if not items:
                return None

            item = items[0]

            # Verify user ownership
            if item.get('userId') != self.user_id:
                logger.warning(f"Session {self.config.session_id} belongs to different user")
                return None

            return item

        except Exception as e:
            logger.debug(f"GSI lookup failed: {e}")
            return None

    def _initialize_message_count(self) -> int:
        """
        Initialize message count by querying AgentCore Memory once at startup.

        Returns:
            Initial message count (0 if session is new or if query fails)
        """
        try:
            messages = self.base_manager.list_messages(
                self.config.session_id,
                "default"  # agent_id
            )
            initial_count = len(messages) if messages else 0
            logger.info(f"📊 Initialized message count from AgentCore Memory: {initial_count}")
            return initial_count
        except Exception as e:
            logger.warning(f"Failed to initialize message count: {e}, defaulting to 0")
            return 0

    # =========================================================================
    # Compaction State Persistence
    # =========================================================================

    def _load_compaction_state(self) -> CompactionState:
        """
        Load compaction state from DynamoDB session metadata.

        The session record uses SK pattern: S#ACTIVE#{last_message_at}#{session_id}
        We use the GSI (SessionLookupIndex) to find it by session_id alone.
        """
        if not self.user_id:
            logger.debug("_load_compaction_state: No user_id, returning default state")
            return CompactionState()
        if not self.compaction_config:
            logger.debug("_load_compaction_state: No compaction_config, returning default state")
            return CompactionState()
        if not self.compaction_config.enabled:
            logger.debug("_load_compaction_state: Compaction disabled, returning default state")
            return CompactionState()

        try:
            table = self._get_dynamodb_table()
            if not table:
                logger.warning("_load_compaction_state: No DynamoDB table available")
                return CompactionState()

            # Look up session via GSI since we don't know the exact SK
            session_item = self._get_session_via_gsi(table)
            if not session_item:
                logger.debug(f"_load_compaction_state: No session record found for session {self.config.session_id}")
                return CompactionState()

            # Extract compaction state from session record
            compaction_data = session_item.get('compaction')
            if compaction_data:
                state = CompactionState.from_dict(compaction_data)
                logger.info(
                    f"📍 Loaded compaction state: checkpoint={state.checkpoint}, "
                    f"summary_len={len(state.summary) if state.summary else 0}, "
                    f"last_tokens={state.last_input_tokens}"
                )
                return state
            else:
                logger.debug(f"_load_compaction_state: Session record found but no 'compaction' attribute")

            return CompactionState()

        except Exception as e:
            logger.warning(f"Error loading compaction state: {e}")
            return CompactionState()

    def _save_compaction_state(self, state: CompactionState) -> None:
        """
        Save compaction state to DynamoDB session metadata.

        Uses GSI to find the session record, then updates it with the compaction state.
        """
        if not self.user_id or not self.compaction_config or not self.compaction_config.enabled:
            return

        try:
            table = self._get_dynamodb_table()
            if not table:
                return

            # Look up session via GSI to get the actual PK/SK
            session_item = self._get_session_via_gsi(table)
            if not session_item:
                logger.warning(f"Session record not found, cannot save compaction state")
                return

            pk = session_item.get('PK')
            sk = session_item.get('SK')
            if not pk or not sk:
                logger.warning(f"Session record missing PK/SK, cannot save compaction state")
                return

            # Update with compaction state
            state.updated_at = datetime.now(timezone.utc).isoformat()
            table.update_item(
                Key={'PK': pk, 'SK': sk},
                UpdateExpression='SET compaction = :state',
                ExpressionAttributeValues={
                    ':state': state.to_dict()
                }
            )
            logger.debug(f"💾 Saved compaction state: checkpoint={state.checkpoint}")
        except Exception as e:
            logger.error(f"Error saving compaction state: {e}")

    # =========================================================================
    # LTM Summary Retrieval
    # =========================================================================

    def _get_summarization_strategy_id(self) -> Optional[str]:
        """Get the SUMMARIZATION strategy ID from configuration or discovery."""
        if self.summarization_strategy_id:
            return self.summarization_strategy_id

        try:
            # Try to discover from memory configuration
            response = self.base_manager.memory_client.gmcp_client.get_memory(
                memoryId=self.config.memory_id
            )
            strategies = response.get('memory', {}).get('strategies', [])

            for strategy in strategies:
                if strategy.get('type') == 'SUMMARIZATION':
                    strategy_id = strategy.get('strategyId', '')
                    self.summarization_strategy_id = strategy_id
                    logger.debug(f"Discovered SUMMARIZATION strategy: {strategy_id}")
                    return strategy_id

            return None

        except Exception as e:
            logger.warning(f"Failed to get SUMMARIZATION strategy ID: {e}")
            return None

    def _retrieve_session_summaries(self) -> List[str]:
        """Retrieve session summaries from AgentCore LTM."""
        strategy_id = self._get_summarization_strategy_id()
        if not strategy_id:
            return []

        try:
            import boto3

            namespace = (
                f"/strategies/{strategy_id}"
                f"/actors/{self.config.actor_id}"
                f"/sessions/{self.config.session_id}"
            )

            client = boto3.client('bedrock-agentcore', region_name=self.region_name)
            response = client.list_memory_records(
                memoryId=self.config.memory_id,
                namespace=namespace,
                maxResults=100
            )

            records = response.get('memoryRecordSummaries', [])
            summaries = []

            for record in records:
                content = record.get("content", {})
                if isinstance(content, dict):
                    text = content.get("text", "").strip()
                    if text:
                        summaries.append(text)

            if summaries:
                logger.info(f"📋 Retrieved {len(summaries)} summaries from LTM")

            return summaries

        except Exception as e:
            logger.warning(f"Failed to retrieve summaries: {e}")
            return []

    def _generate_fallback_summary(self, messages: List[Dict]) -> Optional[str]:
        """Generate a fallback summary when LTM summaries unavailable."""
        if not messages:
            return None

        try:
            key_points = []
            for msg in messages:
                role = msg.get('role', '')
                content = msg.get('content', [])

                if role == 'user' and isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and 'text' in block:
                            text = block['text']
                            # Skip tool results
                            if 'toolResult' not in block:
                                first_line = text.split('\n')[0][:100]
                                if first_line and not first_line.startswith('<'):
                                    key_points.append(f"- User asked about: {first_line}")
                            break

            if key_points:
                summary = "Previous conversation topics:\n" + "\n".join(key_points[-10:])
                logger.debug(f"📝 Generated fallback summary with {len(key_points)} points")
                return summary

        except Exception as e:
            logger.warning(f"Failed to generate fallback summary: {e}")

        return None

    # =========================================================================
    # Message Processing Helpers
    # =========================================================================

    def _has_tool_result(self, message: Dict) -> bool:
        """Check if message contains toolResult block."""
        content = message.get('content', [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and 'toolResult' in block:
                    return True
        return False

    def _find_valid_cutoff_indices(self, messages: List[Dict]) -> List[int]:
        """
        Find valid cutoff points (user message indices that start turns).

        A valid cutoff is a user message that is NOT a tool result.
        """
        valid_indices = []
        for i, msg in enumerate(messages):
            if msg.get('role') == 'user' and not self._has_tool_result(msg):
                valid_indices.append(i)
        return valid_indices

    def _find_protected_indices(self, messages: List[Dict], protected_turns: int) -> set:
        """Find message indices that should be protected from truncation."""
        if protected_turns <= 0:
            return set()

        turn_start_indices = self._find_valid_cutoff_indices(messages)

        if not turn_start_indices:
            return set()

        turns_to_protect = min(protected_turns, len(turn_start_indices))
        protected_start_idx = turn_start_indices[-turns_to_protect]

        return set(range(protected_start_idx, len(messages)))

    # =========================================================================
    # Truncation (Stage 1 Compaction)
    # =========================================================================

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text with indicator."""
        if len(text) <= max_length:
            return text
        return text[:max_length] + f"\n... [truncated, {len(text) - max_length} chars removed]"

    def _truncate_tool_contents(
        self,
        messages: List[Dict],
        protected_indices: Optional[set] = None
    ) -> tuple:
        """
        Stage 1 Compaction: Truncate long tool inputs/results and replace images.

        Returns:
            Tuple of (modified_messages, truncation_count, chars_saved)
        """
        if not self.compaction_config:
            return messages, 0, 0

        max_len = self.compaction_config.max_tool_content_length
        modified_messages = copy.deepcopy(messages)
        truncation_count = 0
        total_chars_saved = 0

        if protected_indices is None:
            protected_indices = set()

        for msg_idx, msg in enumerate(modified_messages):
            if msg_idx in protected_indices:
                continue

            content = msg.get('content', [])
            if not isinstance(content, list):
                continue

            for block_idx, block in enumerate(content):
                if not isinstance(block, dict):
                    continue

                # Handle image blocks - replace with placeholder
                if 'image' in block:
                    image_data = block['image']
                    image_format = image_data.get('format', 'unknown')
                    source = image_data.get('source', {})
                    original_bytes = source.get('bytes', b'')
                    original_size = len(original_bytes) if isinstance(original_bytes, bytes) else 0

                    content[block_idx] = {
                        'text': f'[Image placeholder: format={image_format}, original_size={original_size} bytes]'
                    }
                    truncation_count += 1
                    total_chars_saved += original_size

                # Handle toolUse input
                elif 'toolUse' in block:
                    tool_use = block['toolUse']
                    tool_input = tool_use.get('input', {})

                    if isinstance(tool_input, dict):
                        input_str = json.dumps(tool_input, ensure_ascii=False)
                        if len(input_str) > max_len:
                            original_len = len(input_str)
                            tool_use['input'] = {
                                "_truncated": self._truncate_text(input_str, max_len)
                            }
                            truncation_count += 1
                            total_chars_saved += original_len - max_len
                    elif isinstance(tool_input, str) and len(tool_input) > max_len:
                        original_len = len(tool_input)
                        tool_use['input'] = self._truncate_text(tool_input, max_len)
                        truncation_count += 1
                        total_chars_saved += original_len - max_len

                # Handle toolResult content
                elif 'toolResult' in block:
                    tool_result = block['toolResult']
                    result_content = tool_result.get('content', [])

                    if isinstance(result_content, list):
                        for result_idx, result_block in enumerate(result_content):
                            if not isinstance(result_block, dict):
                                continue

                            # Replace images with placeholder
                            if 'image' in result_block:
                                image_data = result_block['image']
                                image_format = image_data.get('format', 'unknown')
                                source = image_data.get('source', {})
                                original_bytes = source.get('bytes', b'')
                                original_size = len(original_bytes) if isinstance(original_bytes, bytes) else 0

                                result_content[result_idx] = {
                                    'text': f'[Image placeholder: format={image_format}, original_size={original_size} bytes]'
                                }
                                truncation_count += 1
                                total_chars_saved += original_size

                            # Truncate text
                            elif 'text' in result_block:
                                text = result_block['text']
                                if len(text) > max_len:
                                    original_len = len(text)
                                    result_block['text'] = self._truncate_text(text, max_len)
                                    truncation_count += 1
                                    total_chars_saved += original_len - max_len

                            # Truncate JSON
                            elif 'json' in result_block:
                                json_content = result_block['json']
                                json_str = json.dumps(json_content, ensure_ascii=False)
                                if len(json_str) > max_len:
                                    original_len = len(json_str)
                                    result_block.pop('json')
                                    result_block['text'] = self._truncate_text(json_str, max_len)
                                    truncation_count += 1
                                    total_chars_saved += original_len - max_len

        if truncation_count > 0:
            logger.info(f"✂️ Truncated {truncation_count} items, saved ~{total_chars_saved:,} chars")

        return modified_messages, truncation_count, total_chars_saved

    # =========================================================================
    # Summary Injection
    # =========================================================================

    def _prepend_summary_to_first_message(
        self,
        messages: List[Dict],
        summary: str
    ) -> List[Dict]:
        """Prepend summary to the first user message's text content."""
        if not messages or not summary:
            return messages

        modified_messages = copy.deepcopy(messages)
        first_msg = modified_messages[0]

        if first_msg.get('role') != 'user':
            return messages

        summary_prefix = (
            "<conversation_summary>\n"
            "The following is a summary of our previous conversation:\n\n"
            f"{summary}\n\n"
            "Please continue the conversation with this context in mind.\n"
            "</conversation_summary>\n\n"
        )

        content = first_msg.get('content', [])
        if isinstance(content, list) and len(content) > 0:
            for block in content:
                if isinstance(block, dict) and 'text' in block:
                    block['text'] = summary_prefix + block['text']
                    return modified_messages

            # No text block found, insert one
            content.insert(0, {'text': summary_prefix.rstrip()})
            first_msg['content'] = content

        return modified_messages

    # =========================================================================
    # Initialization with Compaction
    # =========================================================================

    def initialize(self, agent: "Agent") -> None:
        """
        Initialize agent with two-feature compaction.

        This method:
        1. Delegates to base manager for basic initialization
        2. Loads compaction state from DynamoDB
        3. Applies checkpoint (skips old messages, prepends summary)
        4. Applies truncation to tool contents
        """
        # First, let base manager do its initialization
        self.base_manager.initialize(agent)

        # If compaction is disabled, we're done
        if not self.compaction_config or not self.compaction_config.enabled:
            return

        # Get messages that base manager loaded
        all_messages = agent.messages or []
        self._total_message_count_at_init = len(all_messages)

        if not all_messages:
            self.compaction_state = CompactionState()
            self._valid_cutoff_indices = []
            self._all_messages_for_summary = []
            return

        # Cache for checkpoint calculation later
        self._all_messages_for_summary = [copy.deepcopy(m) for m in all_messages]
        self._valid_cutoff_indices = self._find_valid_cutoff_indices(all_messages)

        # Load compaction state
        self.compaction_state = self._load_compaction_state()
        checkpoint = self.compaction_state.checkpoint
        summary = self.compaction_state.summary

        logger.info(
            f"📍 Compaction init: checkpoint={checkpoint}, "
            f"total_messages={len(all_messages)}, "
            f"has_summary={summary is not None}"
        )

        # Track compaction stage for logging
        stage = "none"
        messages_to_process = all_messages

        # Apply checkpoint if set
        if checkpoint > 0 and checkpoint < len(all_messages):
            messages_to_process = all_messages[checkpoint:]
            logger.info(
                f"📍 Checkpoint applied: loading {len(messages_to_process)} "
                f"of {len(all_messages)} messages (checkpoint={checkpoint})"
            )

            # Prepend summary if available
            if summary and messages_to_process:
                messages_to_process = self._prepend_summary_to_first_message(
                    messages_to_process, summary
                )
                logger.info(f"📋 Prepended summary ({len(summary)} chars)")

            stage = "checkpoint"

        # Apply truncation (always when compaction enabled)
        protected_indices = self._find_protected_indices(
            messages_to_process,
            self.compaction_config.protected_turns
        )

        truncated_messages, truncation_count, _ = self._truncate_tool_contents(
            messages_to_process,
            protected_indices=protected_indices
        )

        if truncation_count > 0:
            stage = "checkpoint+truncation" if stage == "checkpoint" else "truncation"

        # Set processed messages on agent
        agent.messages = truncated_messages

        logger.info(
            f"✅ Compaction initialized: stage={stage}, "
            f"original={self._total_message_count_at_init}, "
            f"final={len(truncated_messages)}, "
            f"truncations={truncation_count}"
        )

    # =========================================================================
    # Post-Turn Update (Stage 2 Compaction Trigger)
    # =========================================================================

    async def update_after_turn(self, input_tokens: int) -> None:
        """
        Update compaction state after a turn completes.

        Called by StreamCoordinator with input token count from model response.
        Triggers checkpoint creation when token threshold exceeded.

        Args:
            input_tokens: Total input token count from this turn
        """
        if not self.compaction_config or not self.compaction_config.enabled:
            return

        if self.compaction_state is None:
            self.compaction_state = CompactionState()

        # Always update token count
        self.compaction_state.last_input_tokens = input_tokens

        # Check if threshold exceeded
        if input_tokens <= self.compaction_config.token_threshold:
            self._save_compaction_state(self.compaction_state)
            return

        logger.info(
            f"🔍 Threshold exceeded: {input_tokens:,} > "
            f"{self.compaction_config.token_threshold:,}"
        )

        # Fetch fresh messages from AgentCore Memory
        # The cached indices from initialize() are stale - new messages were added
        try:
            raw_messages = self.base_manager.list_messages(
                self.config.session_id,
                "default"  # agent_id
            )
            if not raw_messages:
                logger.info("⚠️ No messages in session, skipping checkpoint")
                self._save_compaction_state(self.compaction_state)
                return

            # Convert SessionMessage objects to dicts
            all_messages = []
            for msg in raw_messages:
                if hasattr(msg, 'message'):
                    # Wrapped format: {'message': {...}, 'message_id': ...}
                    msg_data = msg.message if hasattr(msg.message, '__dict__') else msg.message
                    if hasattr(msg_data, 'model_dump'):
                        all_messages.append(msg_data.model_dump())
                    elif isinstance(msg_data, dict):
                        all_messages.append(msg_data)
                elif hasattr(msg, 'model_dump'):
                    all_messages.append(msg.model_dump())
                elif isinstance(msg, dict):
                    all_messages.append(msg)

            logger.info(f"📥 Fetched {len(all_messages)} messages for compaction calculation")

        except Exception as e:
            logger.warning(f"Failed to fetch messages for compaction: {e}")
            self._save_compaction_state(self.compaction_state)
            return

        # Recalculate valid cutoff indices from fresh messages
        valid_cutoff_indices = self._find_valid_cutoff_indices(all_messages)

        if not valid_cutoff_indices:
            logger.info("⚠️ No valid cutoff points found in messages")
            self._save_compaction_state(self.compaction_state)
            return

        total_turns = len(valid_cutoff_indices)
        protected_turns = self.compaction_config.protected_turns

        logger.info(f"📊 Found {total_turns} turns, protecting last {protected_turns}")

        if total_turns <= protected_turns:
            logger.info(
                f"⚠️ Only {total_turns} turns (need > {protected_turns}), "
                f"keeping all messages"
            )
            self._save_compaction_state(self.compaction_state)
            return

        # Calculate new checkpoint at the oldest protected turn boundary
        new_checkpoint = valid_cutoff_indices[-protected_turns]
        current_checkpoint = self.compaction_state.checkpoint

        if new_checkpoint <= current_checkpoint:
            logger.debug(f"Checkpoint unchanged: {current_checkpoint}")
            self._save_compaction_state(self.compaction_state)
            return

        logger.info(
            f"🔄 Checkpoint update: {current_checkpoint} → {new_checkpoint}"
        )

        # Update cached data for summary generation
        self._valid_cutoff_indices = valid_cutoff_indices
        self._all_messages_for_summary = all_messages

        # Generate summary for compacted messages
        messages_to_summarize = (
            self._all_messages_for_summary[:new_checkpoint]
            if self._all_messages_for_summary else []
        )

        # Try LTM summaries first, fall back to simple summary
        summaries = self._retrieve_session_summaries()
        if summaries:
            summary = "\n\n".join(summaries)
        else:
            summary = self._generate_fallback_summary(messages_to_summarize)

        # Update state
        self.compaction_state.checkpoint = new_checkpoint
        self.compaction_state.summary = summary

        # Persist
        self._save_compaction_state(self.compaction_state)

        logger.info(
            f"✅ Compaction checkpoint set: {new_checkpoint}, "
            f"summary_length={len(summary) if summary else 0}"
        )

    # =========================================================================
    # Session Manager Interface
    # =========================================================================

    def flush(self) -> Optional[int]:
        """
        Flush is now a no-op since we don't buffer messages.

        Returns:
            Message ID of the last message, or None if no messages
        """
        if self.message_count > 0:
            return self.message_count - 1
        return None

    def append_message(self, message, agent, **kwargs):
        """
        Pass message through to base manager and track message count.

        Args:
            message: Message from Strands framework
            agent: Agent instance
            **kwargs: Additional arguments
        """
        if self.cancelled:
            logger.warning(f"🚫 Session cancelled, ignoring message")
            return

        # Delegate to base manager
        self.base_manager.append_message(message, agent, **kwargs)

        # Track message count
        self.message_count += 1

        role = message.get("role", "unknown")
        logger.debug(f"📝 Message persisted (role={role}, count={self.message_count})")

    def register_hooks(self, registry, **kwargs):
        """
        Register hooks with the Strands Agent framework.

        CRITICAL: This method MUST be defined here to prevent the base manager
        from registering its own hooks. We register OUR methods as callbacks.
        """
        from strands.hooks import (
            AgentInitializedEvent,
            MessageAddedEvent,
            AfterInvocationEvent
        )

        logger.info("🔗 Registering hooks (with compaction support)")

        # Register initialization hook - use OUR initialize (with compaction)
        registry.add_callback(
            AgentInitializedEvent,
            lambda event: self.initialize(event.agent)
        )

        # Register message added hook - use OUR append_message
        registry.add_callback(
            MessageAddedEvent,
            lambda event: self.append_message(event.message, event.agent)
        )

        # Register sync hooks - delegate to base manager
        registry.add_callback(
            MessageAddedEvent,
            lambda event: self.base_manager.sync_agent(event.agent)
        )

        registry.add_callback(
            AfterInvocationEvent,
            lambda event: self.base_manager.sync_agent(event.agent)
        )

        # Register LTM retrieval hook
        registry.add_callback(
            MessageAddedEvent,
            lambda event: self.base_manager.retrieve_customer_context(event)
        )

        logger.info("✅ Hooks registered (including LTM retrieval)")

    def __getattr__(self, name):
        """Delegate unknown methods to base AgentCore session manager."""
        return getattr(self.base_manager, name)
