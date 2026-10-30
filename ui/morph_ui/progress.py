"""Optional, prompt-bound runtime observations; history remains authoritative."""
import asyncio
from datetime import datetime, timezone
import json
import math

import aiohttp


class ProgressWatcher:
    # One initial attempt and three retries; reads cannot reset this budget.
    RETRY_DELAYS = (.1, .2, .4)
    CONNECT_TIMEOUT = .75

    def __init__(self, network, url, prompt_id, client_id, graph, callback):
        self.network, self.url = network, url
        self.prompt_id, self.client_id = prompt_id, client_id
        self.nodes = {key: node.get('class_type') for key, node in graph.items()
                      if isinstance(key, str) and isinstance(node, dict)}
        self.callback, self.ready = callback, asyncio.Event()
        self.stopped = False
        self.socket, self.close_task = None, None
        self.progress = dict(event=None, node_id=None, node_type=None, value=None, max=None,
                             percent=None, cached_nodes=[], observed_at=None, connection='connecting')
        self.task = asyncio.create_task(self.run(), name='morph-progress-' + prompt_id)

    async def wait_initial(self):
        # The first handshake already has CONNECT_TIMEOUT. A shorter second
        # deadline could submit while a healthy first connection is still opening.
        await self.ready.wait()

    def emit(self, **fields):
        self.progress.update(fields)
        try:
            if self.callback(dict(self.progress, cached_nodes=list(self.progress['cached_nodes']))) is False:
                self.stopped = True
        except Exception:
            # Optional telemetry must not affect submission or create an unhandled task.
            self.stopped = True

    def observe(self, packet):
        if not isinstance(packet, dict) or not isinstance(packet.get('data'), dict):
            return
        data, event = packet['data'], packet.get('type')
        if data.get('prompt_id') != self.prompt_id:
            return
        fields = {}
        if event in {'executing', 'progress', 'execution_interrupted', 'execution_error'}:
            if event == 'executing' and 'node' not in data:
                return
            node = data.get('node_id') if event in {'execution_interrupted', 'execution_error'} else data.get('node')
            # The terminal executing(node=None) packet is merely a refresh hint.
            if event == 'executing' and node is None:
                fields.update(node_id=None, node_type=None, value=None, max=None, percent=None)
            elif not isinstance(node, str) or node not in self.nodes:
                return
            else:
                fields.update(node_id=node, node_type=self.nodes[node], value=None, max=None, percent=None)
            if event == 'progress':
                value, maximum = data.get('value'), data.get('max')
                if (type(value) not in (int, float) or type(maximum) not in (int, float)
                        or not math.isfinite(value) or not math.isfinite(maximum)
                        or maximum <= 0 or not 0 <= value <= maximum):
                    return
                fields.update(value=value, max=maximum, percent=value / maximum * 100)
        elif event == 'execution_cached':
            nodes = data.get('nodes')
            if not isinstance(nodes, list):
                return
            fields.update(cached_nodes=list(dict.fromkeys(node for node in nodes if isinstance(node, str) and node in self.nodes)))
        elif event == 'execution_start':
            fields.update(node_id=None, node_type=None, value=None, max=None, percent=None, cached_nodes=[])
        elif event == 'execution_success':
            fields.update(value=None, max=None, percent=None)
        else:
            return
        self.emit(event=event, observed_at=datetime.now(timezone.utc).isoformat(), **fields)

    async def run(self):
        self.emit(connection='connecting')
        try:
            for attempt in range(len(self.RETRY_DELAYS) + 1):
                if self.stopped:
                    return
                if attempt:
                    self.emit(connection='reconnecting')
                    await asyncio.sleep(self.RETRY_DELAYS[attempt - 1])
                try:
                    socket = await asyncio.wait_for(self.network().ws_connect(
                        self.url, params={'clientId': self.client_id}, heartbeat=20,
                        max_msg_size=1024 * 1024), self.CONNECT_TIMEOUT)
                    self.socket = socket
                    async with socket:
                        self.emit(connection='connected')
                        self.ready.set()
                        async for message in socket:
                            if self.stopped:
                                return
                            if message.type == aiohttp.WSMsgType.TEXT:
                                try:
                                    self.observe(json.loads(message.data))
                                except (ValueError, TypeError, OverflowError):
                                    continue
                                if self.stopped:
                                    return
                            elif message.type in {aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}:
                                break
                except (aiohttp.ClientError, OSError, TimeoutError):
                    pass
                finally:
                    self.socket = None
                    self.ready.set()
            if not self.stopped:
                self.emit(connection='unavailable')
        finally:
            self.ready.set()

    def stop(self):
        self.stopped = True
        if self.close_task is None:
            self.close_task = asyncio.create_task(self.shutdown(), name='morph-progress-close-' + self.prompt_id)

    async def shutdown(self):
        # Complete the websocket close handshake before cancelling its reader.
        # Cancelling the reader first can abort its Windows socket transport.
        if self.socket is not None:
            try:
                await asyncio.wait_for(self.socket.close(), .5)
            except (aiohttp.ClientError, OSError, TimeoutError):
                pass
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)

    async def close(self):
        self.stop()
        await self.close_task
