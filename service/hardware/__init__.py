"""Auto-discover all RazerDevice subclasses in this package."""

import importlib
import pkgutil
import pathlib
from typing import Type

from .device_base import RazerDevice

_DEVICE_BY_PID: dict[int, Type[RazerDevice]] = {}


def _load_all() -> None:
    pkg_dir = pathlib.Path(__file__).parent
    for mod_info in pkgutil.iter_modules([str(pkg_dir)]):
        if mod_info.name == "device_base":
            continue
        mod = importlib.import_module(f".{mod_info.name}", package=__name__)
        for attr in vars(mod).values():
            if (
                isinstance(attr, type)
                and issubclass(attr, RazerDevice)
                and attr is not RazerDevice
                and getattr(attr, "USB_PID", None) is not None
            ):
                _DEVICE_BY_PID[attr.USB_PID] = attr


_load_all()


def get_device_class(pid: int) -> Type[RazerDevice] | None:
    return _DEVICE_BY_PID.get(pid)


def all_supported_pids() -> list[int]:
    return list(_DEVICE_BY_PID.keys())
