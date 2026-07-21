from __future__ import annotations

from collections.abc import Callable


class PayloadUpcaster:
    def __init__(self) -> None:
        self._upcasters: dict[tuple[int, int], Callable[[dict], dict]] = {}
        self._max_version: int = 1

    def register(self, from_version: int, to_version: int, fn: Callable[[dict], dict]) -> None:
        if to_version != from_version + 1:
            raise ValueError(f"upcaster must step by 1, got {from_version}->{to_version}")
        self._upcasters[(from_version, to_version)] = fn
        if to_version > self._max_version:
            self._max_version = to_version

    def unregister(self, from_version: int, to_version: int) -> None:
        self._upcasters.pop((from_version, to_version), None)
        if self._upcasters:
            self._max_version = max(key[1] for key in self._upcasters)
        else:
            self._max_version = 1

    def current_version(self) -> int:
        return self._max_version

    def migrate(
        self,
        payload: dict,
        *,
        from_version: int,
        to_version: int | None = None,
    ) -> tuple[dict, int]:
        if to_version is None:
            to_version = self._max_version
        if from_version == to_version:
            return dict(payload), from_version
        if from_version > to_version:
            raise ValueError(f"downcast not supported: {from_version} > {to_version}")
        current = dict(payload)
        version = from_version
        while version < to_version:
            key = (version, version + 1)
            if key not in self._upcasters:
                raise ValueError(f"no upcaster registered for {key}")
            current = self._upcasters[key](current)
            version += 1
        return current, version


_DEFAULT_UPCASTER = PayloadUpcaster()


def get_default_upcaster() -> PayloadUpcaster:
    return _DEFAULT_UPCASTER


def current_payload_version() -> int:
    return _DEFAULT_UPCASTER.current_version()


def normalize_payload(
    payload: dict,
    *,
    from_version: int,
    to_version: int | None = None,
) -> dict:
    normalized, _ = _DEFAULT_UPCASTER.migrate(payload, from_version=from_version, to_version=to_version)
    return normalized
