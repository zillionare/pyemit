import asyncio
import unittest

import pyemit.emit as e
from tests.helper import async_test

import logging

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)

_received_test_decorator_msgs = 0


@e.on('test_decorator')
async def on_test_decorator(msg):
    global _received_test_decorator_msgs
    logger.info("on_test_decorator")
    _received_test_decorator_msgs += 1


class TestEmit(unittest.TestCase):

    def setUp(self) -> None:
        self.echo_times = 0
        e._started = False

    def tearDown(self) -> None:
        asyncio.run(e.stop())

    @async_test
    async def test_decorator(self):
        await e.start(engine=e.Engine.REDIS, dsn="redis://localhost")
        logger.info(f"{e._registry}")
        await e.emit("test_decorator")
        await asyncio.sleep(0.2)
        self.assertEqual(_received_test_decorator_msgs, 1)

    async def on_in_process(self, msg):
        # self.assertEqual(msg, "in-process")
        print(msg)

    @async_test
    async def test_in_process_engine(self):
        e.register('test_in_process', self.on_in_process)
        await e.start(e.Engine.IN_PROCESS)
        e.register("test_after_start", self.on_in_process)

        await asyncio.sleep(0.1)
        await e.emit('test_in_process', {"msg": "in-process"})
        await e.emit("test_after_start", {"msg": "after-start"})
        await asyncio.sleep(0.5)

    async def on_echo(self, msg):
        logger.info("on_echo received: %s", msg)
        self.echo_times += 1
        if self.echo_times < 1:
            await e.emit('echo', msg)

    @async_test
    async def test_aio_redis_engine(self):
        await e.start(e.Engine.REDIS, dsn="redis://localhost")
        e.register('echo', self.on_echo)

        await asyncio.sleep(0.5)
        await e.emit('echo', {"msg": "new message 1.0"})
        # receiver will receive None
        await e.emit('echo')
        # this will cause no problem. sender can send any message out
        await e.emit("not registered")
        await asyncio.sleep(1)

    @async_test
    async def test_heart_beat(self):
        e.register("hi", self.on_echo)
        await e.start(e.Engine.REDIS, heart_beat=0.5, dsn="redis://localhost")
        await asyncio.sleep(1)

    async def rpc_handler(self, msg):
        if msg['command'] == 'add':
            msg["result"] = msg["count"] + 1
            msg.pop('count')

            await e.rpc_respond(msg)

    @async_test
    async def test_redis_rpc_call(self):
        e.rpc_register_handler(self.rpc_handler)
        await e.start(e.Engine.REDIS, dsn="redis://localhost")
        response = await e.rpc_send({"command": "add", "count": 0})
        self.assertEqual(1, response['result'])

        await asyncio.sleep(0.1)

    @async_test
    async def test_inprocess_rpc_call(self):
        e.rpc_register_handler(self.rpc_handler)
        await e.start(dsn="redis://localhost")
        response = await e.rpc_send({"command": "add", "count": 0})
        self.assertEqual(1, response['result'])

        await asyncio.sleep(0.1)

    @async_test
    async def test_inprocess_stop(self):
        e.register("test_stop", self.on_echo)
        await e.start()
        await e.stop()

    @async_test
    async def test_redis_stop(self):
        e.register("test_stop", self.on_echo)
        await e.start(engine=e.Engine.REDIS, heart_beat=0.3, dsn="redis://localhost")

        await e.emit("test_stop", {"msg": "check this in log"})
        await asyncio.sleep(0.1)
        e.unsubscribe("test_stop", self.on_echo)
        await e.emit("test_stop", {"msg": "nobody will handle this"})