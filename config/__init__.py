from microapi.di import ServiceProvider
from microapi.event import EventDispatcher
from microapi.event_subscriber import RoutingEventSubscriber, SecurityEventSubscriber, SerializeEventSubscriber
from microapi.router import Router
from microapi.http import Client, ClientFactory
from microapi.di import Container
from microapi.security import Security, TokenStore, Firewall, DefaultVoter, JwtTokenResolver, UserResolver, \
    JwtUserResolver


class FrameworkServiceProvider(ServiceProvider):
    def services(self):
        # HTTP
        yield Router, lambda _: Router(_.tagged_generator('controller'))
        yield EventDispatcher, lambda _: EventDispatcher(_.tagged_generator('event_subscriber'))
        yield RoutingEventSubscriber
        yield SerializeEventSubscriber

        # Util
        yield Client, FrameworkServiceProvider.client_factory

    @staticmethod
    async def client_factory(_: Container) -> Client:
        client_factory = await _.get(ClientFactory)
        return client_factory.create()


class SecurityServiceProvider(ServiceProvider):
    def __init__(self, firewall_paths: dict = None, user_resolver: UserResolver = None, jwt_secret: str = None):
        self.firewall_paths = firewall_paths
        self.jwt_secret = jwt_secret
        self.user_resolver = user_resolver

    def services(self):
        user_resolver = self.user_resolver
        if self.jwt_secret is not None:
            if user_resolver is None:
                user_resolver = JwtUserResolver
            yield JwtUserResolver, lambda _: JwtUserResolver(self.jwt_secret)
            yield JwtTokenResolver, SecurityServiceProvider.jwt_token_resolver_factory(self.jwt_secret)

        # Security
        yield TokenStore
        yield Firewall, SecurityServiceProvider.firewall_factory(user_resolver, self.firewall_paths)
        yield Security, SecurityServiceProvider.security_factory
        yield SecurityEventSubscriber
        yield DefaultVoter

    @staticmethod
    async def security_factory(_: Container) -> Security:
        token_store = await _.get(TokenStore)
        return Security(token_store, _.tagged_generator('security_voter'))

    @staticmethod
    def jwt_token_resolver_factory(jwt_secret: str = None):
        async def factory(_: Container) -> JwtTokenResolver:
            return JwtTokenResolver(jwt_secret)

        return factory

    @staticmethod
    def firewall_factory(user_resolver_service = None, paths = None):
        if paths is None:
            paths = {}

        async def factory(_: Container) -> Firewall:
            security = await _.get(Security)
            token_store = await _.get(TokenStore)
            user_resolver = None
            if user_resolver_service is not None:
                user_resolver = await _.get(user_resolver_service)
            firewall = Firewall(security, token_store, user_resolver, _.tagged_generator('security_token_resolver'))

            for path, role in paths.items():
                await firewall.add(path, role)

            return firewall

        return factory
