"""Register all RazerDevice subclasses from this package."""

from typing import Type

from .device_base import RazerDevice
from . import keyboards, mouse  # explicit — pkgutil.iter_modules breaks in frozen exes

_DEVICE_BY_PID: dict[int, Type[RazerDevice]] = {}

for _mod in (keyboards, mouse):
    for _attr in vars(_mod).values():
        if (
            isinstance(_attr, type)
            and issubclass(_attr, RazerDevice)
            and _attr is not RazerDevice
            and getattr(_attr, "USB_PID", None) is not None
        ):
            _DEVICE_BY_PID[_attr.USB_PID] = _attr



def get_device_class(pid: int) -> Type[RazerDevice] | None:
    return _DEVICE_BY_PID.get(pid)


def all_supported_pids() -> list[int]:
    return list(_DEVICE_BY_PID.keys())
