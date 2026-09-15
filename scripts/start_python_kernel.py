"""Start the local notebook kernel with an explicit asyncio event loop."""

import asyncio
import inspect

from ipykernel.ipkernel import IPythonKernel
from ipykernel.kernelapp import IPKernelApp


class NotebookKernel(IPythonKernel):
    """Use the awaitable shutdown interface requested by ipykernel 7.3."""

    async def do_shutdown(self, restart):
        result = super().do_shutdown(restart)
        return await result if inspect.isawaitable(result) else result


if __name__ == "__main__":
    app = IPKernelApp.instance(kernel_class=NotebookKernel)
    app.initialize()
    # Shell initialization can reset the current loop. Set it immediately
    # before Tornado starts instead of relying on deprecated implicit creation.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        app.start()
    finally:
        loop.close()
        asyncio.set_event_loop(None)
