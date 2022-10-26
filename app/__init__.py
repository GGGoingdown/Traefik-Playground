#######
#   Application Metadata
#######
__VERSION__ = "0.0.1"
__TITLE__ = "FastAPITraefik"
__DESCRIPTION__ = "Traefik tutorial"
__DOCS_URL__ = None
__ROOT_PATH__ = "/api/v1"
################################################
import sys
import sentry_sdk
import socketio
from loguru import logger
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from socketio.asyncio_pubsub_manager import AsyncPubSubManager


# Settings
from app import exceptions
from app.config import settings

# Sentry
def add_sentry_middleware(app: FastAPI, *, release_name: str) -> None:
    from app.middleware import CustomSentryAsgiMiddleware

    def before_send(event, hint):
        if "exc_info" in hint:
            exc_type, exc_value, tb = hint["exc_info"]
            if isinstance(exc_value, ValueError):
                logger.warning(f"Exception: {exc_type} - Value: {exc_value}")
                return None
        return event

    # Initial sentry and add middleware
    logger.info("--- Initial Sentry ---")
    sentry_sdk.init(
        settings.sentry.dns,
        traces_sample_rate=settings.sentry.trace_sample_rates,
        release=f"{release_name}@{__VERSION__}",
        environment=settings.app.env_mode.value,
        before_send=before_send,
    )
    app.add_middleware(CustomSentryAsgiMiddleware)


# Log request
def add_log_middleware(app: FastAPI) -> None:
    from app.middleware import LogRequestsMiddleware, IgnoredRoute

    app.add_middleware(
        LogRequestsMiddleware,
        ignored_routes=[
            IgnoredRoute(path="/health"),  # Health check endpoint
            IgnoredRoute(path="/openapi.json"),  # OpenAPI
        ],
    )


# Exceptions
def add_exceptions(app: FastAPI) -> None:
    from tortoise.exceptions import DoesNotExist, IntegrityError

    @app.exception_handler(DoesNotExist)
    async def doesnotexist_exception_handler(request: Request, exc: DoesNotExist):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)}
        )

    @app.exception_handler(IntegrityError)
    async def integrityerror_exception_handler(request: Request, exc: IntegrityError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
            headers={"X-Error": "IntegrityError"},
        )

    @app.exception_handler(exceptions.BaseInternalServiceException)
    async def internalerror_exception_handler(
        request: Request, exc: exceptions.BaseInternalServiceException
    ):
        _error_message = str(exc.error_message)
        return JSONResponse(
            status_code=status.HTTP_418_IM_A_TEAPOT,
            content={"detail": str(exc)},
            headers={"X-Error": _error_message},
        )


def create_socketio(
    app: FastAPI, socketio_client: AsyncPubSubManager
) -> socketio.AsyncServer:
    logger = True
    engineio_logger = True

    sio = socketio.AsyncServer(
        async_mode="asgi",
        client_manager=socketio_client,
        logger=logger,
        engineio_logger=engineio_logger,
        cors_allowed_origins="*",
    )
    # # * Register namespace * #
    from app.routers import (
        SocketIONamespace,
    )

    sio.register_namespace(SocketIONamespace("/so"))

    asgi = socketio.ASGIApp(
        socketio_server=sio,
    )
    app.mount("/ws/socket", asgi)


def create_app() -> FastAPI:
    app = FastAPI(
        title=__TITLE__,
        description=__DESCRIPTION__,
        version=__VERSION__,
        docs_url=__DOCS_URL__,
        root_path=__ROOT_PATH__,
    )

    # Routers
    from app import routers

    app.include_router(routers.health_router)
    app.include_router(routers.authentication_router)
    app.include_router(routers.user_router)
    app.include_router(routers.ws_router)

    # Dependency injection
    from app import security
    from app.containers import Application

    container = Application()
    container.config.from_pydantic(settings)
    container.wire(modules=[sys.modules[__name__], security, routers.auth, routers.ws])

    app.container = container

    @app.on_event("startup")
    async def startup_event():
        logger.info("--- Startup Event ---")
        #! If resource with async function, change init_resources to await
        await app.container.service.init_resources()

        socketio_client = app.container.gateway.socketio_client()
        create_socketio(app, socketio_client=socketio_client)

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("--- Shutdown Event ---")
        #! If resource with async function, change init_resources to await
        await app.container.service.shutdown_resources()

    # Sentry middleware
    if settings.sentry.dns:
        add_sentry_middleware(app, release_name=settings.app.application_name)

    # Log request middleware
    add_log_middleware(app)

    # Customize Exceptions
    add_exceptions(app)

    return app
