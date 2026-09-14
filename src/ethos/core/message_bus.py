"""
ETHOS Async Message Bus
High-throughput event-driven pub/sub communication for multi-agent audio workflows.
"""

import asyncio
import logging
import secrets
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


def generate_trace_id() -> str:
    """Generate a standard 128-bit W3C hex trace ID."""
    return secrets.token_hex(16)


def generate_span_id() -> str:
    """Generate a standard 64-bit W3C hex span ID."""
    return secrets.token_hex(8)


class MessagePriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Message:
    topic: str
    payload: dict[str, Any]
    sender: str
    timestamp: datetime
    priority: MessagePriority = MessagePriority.NORMAL
    correlation_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    trace_context: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.trace_id:
            self.trace_id = generate_trace_id()
        if not self.span_id:
            self.span_id = generate_span_id()
        if "traceparent" not in self.trace_context:
            self.trace_context["traceparent"] = f"00-{self.trace_id}-{self.span_id}-01"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["priority"] = self.priority.value
        return data


class MessageBus:
    """
    Async message bus for agent communication.
    Supports exact and wildcard pub/sub, priority queues, and bounded history.
    """

    def __init__(self, max_history: int = 10000):
        self.subscribers: dict[str, list[Callable]] = {}
        self.message_history: list[Message] = []
        self.max_history = max_history
        self._running = False
        self._message_queue: asyncio.Queue[Message] = asyncio.Queue()

    def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to a topic with a synchronous or asynchronous callback."""
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)
        callback_name = getattr(callback, "__name__", repr(callback))
        logger.debug("Subscribed to %s: %s", topic, callback_name)

    def unsubscribe(self, topic: str, callback: Callable) -> None:
        """Unsubscribe callback from topic."""
        if topic in self.subscribers and callback in self.subscribers[topic]:
            self.subscribers[topic].remove(callback)

    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        sender: str,
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
        trace_context: dict[str, str] | None = None,
    ) -> Message:
        """Publish a message to a topic with distributed trace context."""
        message = Message(
            topic=topic,
            payload=payload,
            sender=sender,
            timestamp=datetime.now(),
            priority=priority,
            correlation_id=correlation_id,
            trace_id=trace_id,
            span_id=span_id,
            trace_context=trace_context or {},
        )

        self.message_history.append(message)
        if len(self.message_history) > self.max_history:
            self.message_history.pop(0)

        await self._message_queue.put(message)
        logger.debug("Published %s from %s [trace=%s]", topic, sender, message.trace_id)
        return message

    async def start(self) -> None:
        """Start background message delivery loop."""
        self._running = True
        logger.debug("Message bus started")

        while self._running:
            try:
                message = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=0.1,
                )
                await self._process_message(message)
                self._message_queue.task_done()
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Message processing error: %s", e)

    async def stop(self) -> None:
        """Stop background message delivery loop."""
        self._running = False
        logger.debug("Message bus stopped")

    async def _process_message(self, message: Message) -> None:
        """Deliver message to matching subscribers."""
        # Wildcard match (e.g. stage1.*)
        parts = message.topic.split(".")
        for i in range(len(parts)):
            pattern = ".".join(parts[: i + 1]) + ".*"
            if pattern in self.subscribers:
                for callback in list(self.subscribers[pattern]):
                    await self._invoke_callback(callback, message)

        # Exact match
        if message.topic in self.subscribers:
            for callback in list(self.subscribers[message.topic]):
                await self._invoke_callback(callback, message)

    async def _invoke_callback(self, callback: Callable, message: Message) -> None:
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(message)
            else:
                callback(message)
        except Exception as e:
            logger.error("Callback error on topic %s: %s", message.topic, e, exc_info=True)

    def get_history(
        self,
        topic: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Message]:
        """Retrieve recent message history with optional filters."""
        filtered = self.message_history
        if topic:
            filtered = [m for m in filtered if m.topic == topic]
        if since:
            filtered = [m for m in filtered if m.timestamp >= since]
        return filtered[-limit:]


_global_message_bus: MessageBus | None = None


def get_message_bus() -> MessageBus:
    """Get the singleton MessageBus instance."""
    global _global_message_bus
    if _global_message_bus is None:
        _global_message_bus = MessageBus()
    return _global_message_bus


async def publish(topic: str, payload: dict[str, Any], sender: str, **kwargs) -> None:
    """Convenience helper to publish to the global message bus."""
    bus = get_message_bus()
    await bus.publish(topic, payload, sender, **kwargs)


def subscribe(topic: str, callback: Callable) -> None:
    """Convenience helper to subscribe to the global message bus."""
    bus = get_message_bus()
    bus.subscribe(topic, callback)
