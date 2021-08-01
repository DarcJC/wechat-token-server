#!/usr/bin/env python
import signal
import sys

from core import settings


def stop():
    sys.exit(-1)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, stop)
    import uvicorn
    uvicorn.run("core:app", workers=4, host=settings.SERVER_HOST, port=settings.SERVER_PORT)
