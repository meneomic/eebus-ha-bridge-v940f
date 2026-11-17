"""Background gRPC stream consumption with reconnect/backoff for the EEBUS integration."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable

import grpc
import grpc.aio
from homeassistant.core import HomeAssistant

from .grpc_client import GrpcChannelManager, is_unimplemented, rpc_error_text
from .session_diagnostics import StreamWorkerDiagnostics

_LOGGER = logging.getLogger(__name__)

STREAM_BACKOFF_BASE_SECONDS = 2.0
STREAM_BACKOFF_MAX_SECONDS = 60.0
STREAM_BACKOFF_JITTER_SECONDS = 3.0

ConsumeFn = Callable[[grpc.aio.Channel], Awaitable[None]]
UnsupportedFn = Callable[[str], None]


class StreamManager:
    """Own the coordinator's long-lived event-stream task lifecycle."""

    def __init__(
        self,
        hass: HomeAssistant,
        channel_manager: GrpcChannelManager,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[float, float], float] = random.uniform,
    ) -> None:
        """Initialize stream lifecycle dependencies."""
        self._hass = hass
        self._channel_manager = channel_manager
        self._sleep = sleep
        self._jitter = jitter
        self._tasks: list[asyncio.Task[None]] = []
        self._restart_tasks: set[asyncio.Task[None]] = set()
        self._restart_attempts: dict[str, int] = {}
        self._unsupported: set[str] = set()
        self._stopping = False
        self._reconnects = 0

    def start(
        self,
        streams: dict[str, ConsumeFn],
        task_name_prefix: str,
        on_unimplemented: UnsupportedFn | None = None,
    ) -> None:
        """Launch one background task per named stream, unless already started."""
        if self._tasks:
            return
        self._stopping = False
        self._unsupported.clear()
        self._restart_attempts.clear()
        for name, consume in streams.items():
            self._launch(name, consume, task_name_prefix, on_unimplemented)

    def _launch(
        self,
        name: str,
        consume: ConsumeFn,
        task_name_prefix: str,
        on_unimplemented: UnsupportedFn | None,
        slot: int | None = None,
    ) -> None:
        """Attach a guarded task, retaining its stable diagnostic slot."""
        task = self._hass.async_create_background_task(
            self._run_stream(name, consume, on_unimplemented),
            name=task_name_prefix.format(name, name=name),
        )
        if slot is None:
            slot = len(self._tasks)
            self._tasks.append(task)
        else:
            self._tasks[slot] = task
        task.add_done_callback(
            lambda done: self._on_stream_done(
                done, slot, name, consume, task_name_prefix, on_unimplemented
            )
        )

    def _on_stream_done(
        self,
        task: asyncio.Task[None],
        slot: int,
        name: str,
        consume: ConsumeFn,
        task_name_prefix: str,
        on_unimplemented: UnsupportedFn | None,
    ) -> None:
        """Recover a worker that escaped its normal retry loop.

        UNIMPLEMENTED is an intentional exit with legacy fallback. All other
        terminal exits are unexpected; a delayed retry avoids a hot loop.
        """
        if (
            self._stopping
            or slot >= len(self._tasks)
            or self._tasks[slot] is not task
            or name in self._unsupported
        ):
            return

        if task.cancelled():
            _LOGGER.warning("EEBUS %s stream unexpectedly cancelled; restarting", name)
        elif (error := task.exception()) is not None:
            _LOGGER.error(
                "EEBUS %s stream terminated unexpectedly; restarting",
                name,
                exc_info=(type(error), error, error.__traceback__),
            )
        else:
            _LOGGER.warning("EEBUS %s stream ended unexpectedly; restarting", name)

        self._reconnects += 1
        attempt = self._restart_attempts.get(name, 0) + 1
        self._restart_attempts[name] = attempt
        delay = min(
            STREAM_BACKOFF_BASE_SECONDS * (2 ** min(attempt - 1, 6)),
            STREAM_BACKOFF_MAX_SECONDS,
        ) + self._jitter(0, STREAM_BACKOFF_JITTER_SECONDS)
        restart = self._hass.async_create_background_task(
            self._restart_after_exit(
                task, slot, name, consume, task_name_prefix, on_unimplemented, delay
            ),
            name=f"{task_name_prefix.format(name, name=name)}_restart",
        )
        self._restart_tasks.add(restart)
        restart.add_done_callback(self._restart_tasks.discard)

    async def _restart_after_exit(
        self,
        previous: asyncio.Task[None],
        slot: int,
        name: str,
        consume: ConsumeFn,
        task_name_prefix: str,
        on_unimplemented: UnsupportedFn | None,
        delay: float,
    ) -> None:
        await self._sleep(delay)
        if (
            not self._stopping
            and slot < len(self._tasks)
            and self._tasks[slot] is previous
        ):
            self._launch(name, consume, task_name_prefix, on_unimplemented, slot)

    async def stop(self) -> None:
        """Cancel workers and pending restarts, including during profile swaps."""
        self._stopping = True
        for task in tuple(self._restart_tasks):
            task.cancel()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(
            *self._restart_tasks, *self._tasks, return_exceptions=True
        )
        self._tasks.clear()
        self._restart_tasks.clear()
        self._restart_attempts.clear()
        self._unsupported.clear()

    def diagnostics(self) -> StreamWorkerDiagnostics:
        """Return non-secret stream lifecycle counters for diagnostics."""
        return StreamWorkerDiagnostics(
            configured=len(self._tasks),
            running=sum(1 for task in self._tasks if not task.done()),
            done=sum(1 for task in self._tasks if task.done()),
            reconnects=self._reconnects,
        )

    async def _run_stream(
        self,
        name: str,
        consume: ConsumeFn,
        on_unimplemented: UnsupportedFn | None = None,
    ) -> None:
        """Consume one stream with reconnect/backoff until cancelled."""
        attempt = 0
        while True:
            try:
                channel = await self._channel_manager.ensure_channel()
                await consume(channel)
                attempt = 0
            except asyncio.CancelledError:
                raise
            except grpc.aio.AioRpcError as err:
                if is_unimplemented(err):
                    _LOGGER.info(
                        "EEBUS %s stream not supported by bridge; relying on polling",
                        name,
                    )
                    if on_unimplemented is not None:
                        on_unimplemented(name)
                    self._unsupported.add(name)
                    return
                attempt += 1
                self._reconnects += 1
                _LOGGER.debug(
                    "EEBUS %s stream ended (%s); scheduling retry",
                    name,
                    rpc_error_text(err),
                )
            except Exception:
                attempt += 1
                self._reconnects += 1
                _LOGGER.exception("EEBUS %s stream failed; scheduling retry", name)

            delay = min(
                STREAM_BACKOFF_BASE_SECONDS * (2 ** max(0, attempt - 1)),
                STREAM_BACKOFF_MAX_SECONDS,
            ) + self._jitter(0, STREAM_BACKOFF_JITTER_SECONDS)
            _LOGGER.debug("Retrying EEBUS %s stream in %.1fs", name, delay)
            await self._sleep(delay)
