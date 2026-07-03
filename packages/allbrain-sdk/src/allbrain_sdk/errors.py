class AllBrainSDKError(RuntimeError):
    """Base exception for SDK failures."""


class AllBrainProtocolError(AllBrainSDKError):
    """The MCP exchange failed or returned an invalid envelope."""


class AllBrainToolError(AllBrainSDKError):
    """AllBrain returned a valid tool response with ``ok=false``."""
