"""
Gateway MCP client integration for managed tool execution
"""
import logging
from typing import List, Optional, Any
from agents.main_agent.integrations.gateway_mcp_client import get_gateway_client_if_enabled

logger = logging.getLogger(__name__)


class GatewayIntegration:
    """Manages Gateway MCP client for Strands Managed Integration"""

    def __init__(self):
        """Initialize gateway integration"""
        self.client: Optional[Any] = None

    def get_client(self, enabled_gateway_tool_ids: List[str]) -> Optional[Any]:
        """
        Get Gateway MCP client if gateway tools are enabled

        Args:
            enabled_gateway_tool_ids: List of gateway tool IDs (e.g., ["gateway_wikipedia", "gateway_arxiv"])

        Returns:
            MCPClient instance or None if not available
        """
        if not enabled_gateway_tool_ids:
            logger.info("No gateway tools requested")
            return None

        # Get Gateway MCP client (Strands 1.16+ Managed Integration)
        # Store as instance variable to keep session alive during Agent lifecycle
        self.client = get_gateway_client_if_enabled(enabled_tool_ids=enabled_gateway_tool_ids)

        if self.client:
            logger.info(f"✅ Gateway MCP client created (Managed Integration with Strands 1.16+)")
            logger.info(f"   Enabled Gateway tool IDs: {enabled_gateway_tool_ids}")
        else:
            logger.warning("⚠️  Gateway MCP client not available")

        return self.client

    def add_to_tool_list(self, tools: List[Any]) -> List[Any]:
        """
        Add Gateway MCP client to tool list if available

        Args:
            tools: Existing list of tools

        Returns:
            Updated tool list with gateway client (if available)
        """
        if self.client:
            # Using Managed Integration (Strands 1.16+) - pass MCPClient directly to Agent
            # Agent will automatically manage lifecycle and filter tools
            tools.append(self.client)
            logger.info(f"✅ Gateway MCP client added to tool list")

        return tools

    def is_available(self) -> bool:
        """
        Check if gateway client is available

        Returns:
            bool: True if gateway client is initialized
        """
        return self.client is not None
