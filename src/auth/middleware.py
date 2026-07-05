from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Iterable
from typing import ClassVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class MiddlewareBase(BaseHTTPMiddleware, ABC):
    _scope_names: ClassVar[tuple[str, ...]]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Before request handling
        gen = self.handle(request)
        if names := self._scope_names:
            missing, getter = object(), (scope := request.scope).get
            if items := {k: v for k in names if (v := getter(k, missing)) != missing}:
                raise RuntimeError(f"Scope is taken before {type(self).__name__} process: {items}")

            scope |= zip(names, await anext(gen), strict=True)
        else:
            await anext(gen)

        # Handle request
        response = await call_next(request)

        # After request handling
        return (await gen.asend(response)) or response

    @abstractmethod
    async def handle(self, request: Request) -> AsyncGenerator[Iterable | Response, Response]:
        """Handle request with 2 yields in 3 stages:
        1. Before request handling
        2. Handle request: <response = yield scope_values> or <yield>
        3. After request handling: <yield response> or <yield>
        Note: `scope_values` is needed only if `_scope_names` exists, `response` is optional
        """
