import copy
import inspect

from microapi.di import tag, Container
from microapi.event import listen
from microapi.http import JsonResponse, RedirectResponse, Request, Response
from microapi.kernel import RequestEvent, ControllerEvent, ExceptionEvent, HttpException, ViewEvent, ResponseEvent
from microapi.router import Router
from microapi.security import Security, Firewall


@tag('event_subscriber')
class RoutingEventSubscriber:
    def __init__(self, container: Container, router: Router):
        self._container = container
        self._router = router

    @listen(RequestEvent)
    def router(self, event: RequestEvent):
        if "_controller" not in event.request.attributes:
            result = self._router.match(event.request)
            if result is not None:
                cls, method_name, params = result
                for key, value in params.items():
                    event.request.attributes[key] = copy.deepcopy(value)

                event.request.attributes["_controller"] = cls
                event.request.attributes["_controller_method"] = method_name

    @listen(ControllerEvent)
    async def controller(self, event: ControllerEvent):
        if "_controller" in event.request.attributes:
            controller_service = event.request.attributes["_controller"]
            if inspect.isclass(controller_service) and "_controller_method" in event.request.attributes:
                controller_method = event.request.attributes["_controller_method"]
                controller_service = await self._container.get(event.request.attributes["_controller"])
                method = getattr(controller_service, controller_method)
                event.controller = method
            elif callable(controller_service):
                event.controller = controller_service

    @listen(ExceptionEvent)
    async def exception(self, event: ExceptionEvent):
        if isinstance(event.exception, HttpException):
            event.response = event.exception.to_response()


@tag('event_subscriber')
class CorsEventSubscriber:
    def __init__(self, origin:str="*", methods:list[str]=None, headers:list[str]=None):
        if origin is not None:
            origin = "*"

        if methods is None:
            methods = ["GET", "POST", "PUT", "PATH", "DELETE", "OPTIONS"]

        if headers is None:
            headers = ["Content-Type", "Authorization"]

        self._origin = origin
        self._methods = methods
        self._headers = headers

    async def cors_headers(self, request: Request):
        return {
            "Access-Control-Allow-Origin": self._origin,
            "Access-Control-Allow-Methods": ", ".join(self._methods),
            "Access-Control-Allow-Headers": ", ".join(self._headers)
        }

    @listen(RequestEvent)
    async def cors(self, event: RequestEvent):
        request = event.request
        if request.method == "OPTIONS":
            event.response = Response("", await self.cors_headers(request))
            return

    @listen(ResponseEvent)
    async def handle_cors(self, event: ResponseEvent):
        request = event.request
        response = event.response

        headers = await self.cors_headers(request)
        for header, value in headers.items():
            event.response.headers[header] = value
        return response


@tag('event_subscriber')
class SecurityEventSubscriber:
    def __init__(self, firewall: Firewall):
        self._firewall = firewall

    @listen(RequestEvent)
    async def authenticate(self, event: RequestEvent):
        await self._firewall.authenticate(event.request)

    @listen(RequestEvent)
    async def firewall(self, event: RequestEvent):
        if not await self._firewall.is_granted(event.request):
            raise HttpException(401, f"Access denied")


@tag('event_subscriber')
class SerializeEventSubscriber:
    @listen(ViewEvent)
    async def serialize(self, event: ViewEvent):
        if event.response is None:
            event.response = JsonResponse(event.controller_result)
