from dataclasses import dataclass


@dataclass
class CustomerContext:
    """Per-session context passed to the agent at invoke time (never chosen by the LLM)."""
    customer_id: int
    customer_name: str
