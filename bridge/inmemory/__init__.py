from microapi.bridge.inmemory.http import ClientExecutor as BridgeClientExecutor
from microapi.bridge.inmemory.kv import StoreManager as BridgeStoreManager
from microapi.bridge.inmemory.kv import StoreReference
from microapi.di import Container, ServiceProvider
from microapi.bridge import CloudContext as FrameworkCloudContext
from microapi.kernel import HttpKernel as FrameworkHttpKernel
from microapi.http import ClientExecutor
from microapi.kv import StoreManager
import os

class CloudContext(FrameworkCloudContext):
    async def kv_store_reference(self, arguments) -> StoreReference:
        if "name" not in arguments:
            raise ValueError("Name must be specified")
        return StoreReference(arguments["name"])

    async def env(self, name, default=None) -> str|None:
        if name not in os.environ:
            return default
        return os.environ[name]


class App(ServiceProvider):
    def __init__(self, kernel: FrameworkHttpKernel = None, container: Container = None, service_providers = None):
        if kernel is not None and (container is not None or service_providers is not None):
            raise RuntimeError("cannot pass both kernel and container or service_providers")

        if kernel is None:
            kernel = FrameworkHttpKernel(container=container, service_providers=service_providers)

        self.kernel = kernel
        self.container = kernel.container
        self.container.provide(self)

    def services(self):
        yield ClientExecutor, lambda _: BridgeClientExecutor()

        async def store_manager_factory(_):
            context = await _.get(FrameworkCloudContext)
            return BridgeStoreManager(context)

        yield StoreManager, store_manager_factory
        yield FrameworkCloudContext, lambda _: CloudContext()
