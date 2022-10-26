from typing import List, Any, Optional, Dict
from loguru import logger
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from socketio.asyncio_namespace import AsyncNamespace
from dependency_injector.wiring import inject, Provide

###
from app import utils, services
from app.containers import Application

router = APIRouter(prefix="/ws")


html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <h2>Your ID: <span id="ws-id"></span></h2>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var client_id = Date.now()
            document.querySelector("#ws-id").textContent = client_id;
            var ws = new WebSocket(`ws://localhost:9000/ws/${client_id}`);
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""

socketioHtml = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
        <script
            src="https://cdn.socket.io/4.4.1/socket.io.min.js"
            integrity="sha384-fKnu0iswBIqkjxrhQCTZ7qlLHOFEgNkRmK2vaO/LbTZSXdJfAu6ewRBdwHPhBo/H"
            crossorigin="anonymous"
        ></script>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <h2>Your ID: <span id="ws-id"></span></h2>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var client_id = Date.now()
            document.querySelector("#ws-id").textContent = client_id;
            const socket_url = `ws://localhost:9000/so`
            const socket = io(socket_url, {
                'path': '/ws/socket/socket.io'
            });

            socket.on('connect', function () {
                console.log("[DeviceSocketIO]::connecting ...");

                if (socket.connected) {
                    console.log("[DeviceSocketIO]::connected successful");
                    setInterval(function () {
                        if (socket.connected !== true) {
                            alert("DeviceSocketIO Disconnected !!")
                            window.location.reload();
                        }
                    }, 3000);
                }
            });

            socket.on("information", function (rsp) {
                console.log(rsp)
            });

            function sendMessage(event) {
                var input = document.getElementById("messageText")
                socket.emit("hello", input.value);
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@router.get("")
async def get():
    return HTMLResponse(html)


@router.get("/so")
async def socketio():
    return HTMLResponse(socketioHtml)


@router.post("/message")
async def send_message():
    client_id = utils.get_shortuuid()
    data = "send from api"
    await manager.broadcast(f"Client #{client_id} says: {data}")


@router.websocket("/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(type(data))
            await manager.send_personal_message(f"You wrote: {data}", websocket)
            await manager.broadcast(f"Client #{client_id} says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client #{client_id} left the chat")


class SocketIONamespace(AsyncNamespace):
    async def on_connect(
        self,
        sid: str,
        environ: Any,
        auth: Optional[Dict],
    ) -> None:
        logger.info("[ComponentSocketIONamespace]:: --- Connect --- ")

    async def on_disconnect(self, sid: str) -> None:
        logger.info("[ComponentSocketIONamespace]:: --- Disconnect ---")

    @inject
    async def on_hello(
        self,
        sid: str,
        message: str,
        socketio_manager: services.SocketioManager = Provide[
            Application.service.socketio_manager
        ],
    ) -> None:
        logger.info(f"Message: {message}")
        await socketio_manager.emit("information", data={"message": message})
