"""API layer.

Each provider is implemented as a class that conforms to the implicit
``LaunchProvider`` protocol:

* ``name`` (property) -> str
* ``next_launches(limit: int)`` -> list[Launch]
* ``next_launch()`` -> Launch | None  (default = ``next_launches(1)[0]``)

The provider is responsible for mapping its own JSON shape onto the
:class:`~launchpad_widget.models.Launch` dataclass.
"""

from .base import LaunchProvider  # re-export
from .launch_library import LaunchLibrary2Provider
from .spacex import SpaceXProvider

__all__ = [
    "LaunchProvider",
    "LaunchLibrary2Provider",
    "SpaceXProvider",
]
