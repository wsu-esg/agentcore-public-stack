"""
System prompt construction for agent.

The active default prompt is resolved on first use (then cached for the
lifetime of the process) using the following priority order:

1. ``AGENT_SYSTEM_PROMPT_SSM_PATH`` env var — path to an SSM Parameter
   Store entry containing the prompt.  The container fetches the value at
   startup via boto3, so the prompt can be updated with
   ``aws ssm put-parameter --overwrite`` + a container restart without any
   CDK redeploy.  Recommended for cloud deployments.
2. ``AGENT_SYSTEM_PROMPT`` env var — the raw prompt text.  Convenient for
   local development where SSM is not available.
3. ``DEFAULT_SYSTEM_PROMPT`` — the generic fallback.  Contains no
   organisation-specific language and is safe to ship as-is.
"""
import logging
import os
from functools import lru_cache
from typing import Optional

from agents.main_agent.utils.timezone import get_current_date_pacific

logger = logging.getLogger(__name__)


DEFAULT_SYSTEM_PROMPT = """You are an AI assistant. You are designed to be helpful, accurate, and \
efficient.

CORE PRINCIPLES:
1. Helpfulness: Address the user's actual need clearly and directly.

2. Honesty: Be transparent about your limitations. Acknowledge when you don't
   have current information or when a question is outside your knowledge.

3. Conciseness: Be efficient in your responses — avoid unnecessary verbosity.

RESPONSE GUIDELINES:
- Respond using markdown.
- You can ONLY use tools that are explicitly provided to you in each conversation.
- When appropriate, you may use KaTeX to render mathematical equations.
- Since the $ character is used to denote a variable in KaTeX, other uses of \
$ should use the HTML entity &#36;
- When the user asks for a diagram or chart, you may use Mermaid to render it.
- Available tools may change throughout the conversation based on user preferences.
- When multiple tools are available, select and use the most appropriate \
combination in the optimal order to fulfil the user's request.
- Break down complex tasks into steps and use multiple tools sequentially or \
in parallel as needed.
- Always explain your reasoning when using tools.
- If you don't have the right tool for a task, clearly inform the user about \
the limitation.

HANDLING MISSING TOOLS:
Users can toggle individual tools on and off from the Tools section of the
model settings panel (the gear icon next to the message input). When a user
asks for something you would normally handle with a tool that isn't currently
available to you, don't just say "I can't do that." Instead:

1. Identify which capability they're asking for in plain language
   (e.g. "spreadsheet analysis", "web browsing", "Python execution",
   "knowledge base search").
2. Tell them that capability isn't active in the current session and suggest
   they enable the matching tool from the Tools panel in settings, then retry
   the request.
3. If you can offer a partial answer without the tool (e.g. explaining a
   formula they could run themselves), do that as a fallback — but lead with
   the tool suggestion so they know the better path exists.

Common user intents and the tools to point at:
- Analyzing spreadsheet/CSV data, aggregations, totals, trends → "Spreadsheet Analysis"
- Listing files attached to the conversation or assistant → "List Spreadsheet Files"
- Running Python code, generating charts or diagrams from data → "Code Interpreter"
- Live web searches, news, current events → the web search tools
- Fetching a specific URL's contents → the URL fetch tool
- Questions answerable from the assistant's knowledge base → the knowledge base search tool

Example response when spreadsheet analysis is disabled and a user asks for a
column total:

> I can compute that for you, but the Spreadsheet Analysis tool isn't
> currently enabled for this conversation. Open the settings panel (gear
> icon next to the message input), enable "Spreadsheet Analysis" under
> Tools, and send the request again — I'll run the aggregation directly
> on the file. Alternatively, you can open the file in Excel and use
> `=SUM(COLUMN_NAME)` on the column.

SPREADSHEET ANALYSIS — DISAMBIGUATION:
When more than one spreadsheet is attached (including the assistant's
knowledge base plus any chat attachments), do not silently pick one for
`analyze_spreadsheet`. The turn preamble will list every available tabular
file when multiple exist. Use that list to decide:

1. If the user named a specific file (or the reference is unambiguous from
   the query), analyze that file and state which one in your response:
   "Analyzing `X.xlsx`: …"
2. If the user's request could reasonably span multiple files (e.g. "total
   X across the ledgers"), either run `analyze_spreadsheet` on each file
   and combine the results, or explain the approach and ask the user which
   files to include.
3. If the reference is ambiguous, ask the user which file they mean
   rather than guessing from RAG chunk ordering.

Always name the file(s) you analyzed in the final response so the user can
audit the choice.

Your goal is to be helpful, accurate, and efficient in completing user \
requests using the available tools."""


@lru_cache(maxsize=1)
def _fetch_from_ssm(ssm_path: str) -> str:
    """Fetch the system prompt from SSM Parameter Store and cache the result.

    The ``@lru_cache`` ensures the SSM API is called exactly once per process
    lifetime.  To pick up a prompt change, update the SSM parameter and
    restart the container — no CDK redeploy required.

    Falls back to ``DEFAULT_SYSTEM_PROMPT`` if the SSM call fails, so a
    misconfigured path degrades gracefully rather than crashing the agent.
    """
    try:
        import boto3

        region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")
        ssm = boto3.client("ssm", region_name=region)
        response = ssm.get_parameter(Name=ssm_path, WithDecryption=False)
        prompt = response["Parameter"]["Value"].strip()
        if prompt:
            logger.info("Loaded system prompt from SSM parameter: %s", ssm_path)
            return prompt
        logger.warning("SSM parameter %s exists but is empty, using default prompt", ssm_path)
    except Exception:
        logger.exception("Failed to fetch system prompt from SSM path %r, using default", ssm_path)
    return DEFAULT_SYSTEM_PROMPT


def _resolve_default_prompt() -> str:
    """Return the prompt to use when no caller-supplied prompt is provided.

    Resolution order:
    1. AGENT_SYSTEM_PROMPT_SSM_PATH — live SSM lookup (cloud deployments)
    2. AGENT_SYSTEM_PROMPT          — raw value in env (local dev)
    3. DEFAULT_SYSTEM_PROMPT        — built-in fallback
    """
    ssm_path = os.environ.get("AGENT_SYSTEM_PROMPT_SSM_PATH", "").strip()
    if ssm_path:
        return _fetch_from_ssm(ssm_path)

    env_prompt = os.environ.get("AGENT_SYSTEM_PROMPT", "").strip()
    if env_prompt:
        logger.info("Using AGENT_SYSTEM_PROMPT from environment")
        return env_prompt

    return DEFAULT_SYSTEM_PROMPT


class SystemPromptBuilder:
    """Builds system prompts with optional date injection."""

    def __init__(self, base_prompt: Optional[str] = None):
        """
        Initialize prompt builder.

        Args:
            base_prompt: Custom base prompt. When None the effective default
                is resolved from ``AGENT_SYSTEM_PROMPT`` (env var) or
                ``DEFAULT_SYSTEM_PROMPT`` (hardcoded fallback).
        """
        self.base_prompt = base_prompt if base_prompt is not None else _resolve_default_prompt()

    def build(self, include_date: bool = True) -> str:
        """
        Build system prompt with optional date.

        Args:
            include_date: Whether to append the current date to the prompt.

        Returns:
            str: Complete system prompt.
        """
        if include_date:
            current_date = get_current_date_pacific()
            prompt = f"{self.base_prompt}\n\nCurrent date: {current_date}"
            logger.info(f"Built system prompt with current date: {current_date}")
            return prompt
        logger.info("Built system prompt without date")
        return self.base_prompt

    @classmethod
    def from_user_prompt(cls, user_prompt: str) -> "SystemPromptBuilder":
        """
        Create builder from a caller-supplied prompt (date already included).

        Args:
            user_prompt: Fully-rendered system prompt from the caller.

        Returns:
            SystemPromptBuilder: Builder configured with the supplied prompt.
        """
        logger.info("Using caller-supplied system prompt")
        return cls(base_prompt=user_prompt)