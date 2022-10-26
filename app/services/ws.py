from typing import Any
from socketio.asyncio_pubsub_manager import AsyncPubSubManager


class SocketioManager:
    __slots__ = ("socketio_client",)

    def __init__(self, socketio_client: AsyncPubSubManager) -> None:
        self.socketio_client = socketio_client

    async def emit(self, event: str, *, data: Any, namespace: str = "/so") -> None:
        await self.socketio_client.emit(event, data=data, namespace=namespace)
