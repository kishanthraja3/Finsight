import asyncio
import json
from typing import Dict, Any, AsyncGenerator

class SSEManager:
    """Manages SSE event queues for active research runs."""
    def __init__(self):
        self.queues: Dict[str, asyncio.Queue] = {}
        self.loop: asyncio.AbstractEventLoop = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    def get_or_create_queue(self, run_id: str) -> asyncio.Queue:
        if run_id not in self.queues:
            self.queues[run_id] = asyncio.Queue()
        return self.queues[run_id]

    def publish_event(self, run_id: str, event_data: Dict[str, Any]):
        """Thread-safe event publishing."""
        if run_id not in self.queues:
            self.queues[run_id] = asyncio.Queue()
        queue = self.queues[run_id]

        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(queue.put_nowait, event_data)
        else:
            try:
                queue.put_nowait(event_data)
            except Exception:
                pass

    async def event_generator(self, run_id: str) -> AsyncGenerator[str, None]:
        queue = self.get_or_create_queue(run_id)
        # Send initial connection ping
        yield f"data: {json.dumps({'type': 'connection', 'run_id': run_id, 'status': 'connected'})}\n\n"

        while True:
            try:
                # Wait for next event with a 15-second heartbeat timeout
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield f"data: {json.dumps(event)}\n\n"
                queue.task_done()
                if event.get("run_status") == "complete" or event.get("type") == "finished":
                    break
            except asyncio.TimeoutError:
                # Heartbeat
                yield f": ping\n\n"
            except asyncio.CancelledError:
                break

    def remove_queue(self, run_id: str):
        self.queues.pop(run_id, None)

sse_manager = SSEManager()
