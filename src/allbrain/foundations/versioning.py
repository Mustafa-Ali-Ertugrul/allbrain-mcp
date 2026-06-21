from __future__ import annotations

from collections.abc import Callable


PAYLOAD_CURRENT_VERSION = 1


class PayloadUpcaster:
    def __init__(self) -> None:
        self._upcasters: dict[tuple[int, int], Callable[[dict], dict]] = {}

    def register(self, from_version: int, to_version: int, fn: Callable[[dict], dict]) -> None:
        if to_version != from_version + 1:
            raise ValueError(f"upcaster must step by 1, got {from_version}->{to_version}")
        self._upcasters[(from_version, to_version)] = fn

    def migrate(
        self,
        payload: dict,
        *,
        from_version: int,
        to_version: int = PAYLOAD_CURRENT_VERSION,
    ) -> tuple[dict, int]:
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


def normalize_payload(
    payload: dict,
    *,
    from_version: int,
    to_version: int = PAYLOAD_CURRENT_VERSION,
) -> dict:
    normalized, _ = _DEFAULT_UPCASTER.migrate(
        payload, from_version=from_version, to_version=to_version
    )
    return normalized
