# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from collections.abc import Generator
    from typing import IO

__version__ = "4.0"


class Client:
    latest = None
    containerCreated = False
    start_exception: Exception | None = None

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.call_args_create_container: list[dict[str, Any]] = []
        self.call_args_create_host_config: list[dict[str, Any]] = []
        self._images: list[dict[str, list[str]]] = [
            {'RepoTags': ['busybox:latest', 'worker:latest', 'tester:latest']}
        ]
        self._pullable = ['alpine:latest', 'tester:latest']
        self._pullCount = 0
        self._containers: dict[str, dict[str, Any]] = {}

        if Client.containerCreated:
            self.create_container("some-default-image")

    def images(self) -> list[dict[str, list[str]]]:
        return self._images

    def start(self, container: str) -> None:
        if self.start_exception is not None:
            raise self.start_exception  # pylint: disable=raising-bad-type

    def stop(self, id: str) -> None:
        pass

    def wait(self, id: str) -> int:
        return 0

    def build(
        self, fileobj: IO[bytes], tag: str, pull: bool, target: str
    ) -> Generator[Any, None, None]:
        if fileobj.read() == b'BUG':
            pass
        elif pull != bool(pull):
            pass
        elif target != "":
            pass
        else:
            logs: list[Any] = []
            yield from logs
            self._images.append({'RepoTags': [tag + ':latest']})

    def pull(self, image: str, *args: Any, **kwargs: Any) -> None:
        if image in self._pullable:
            self._pullCount += 1
            self._images.append({'RepoTags': [image]})

    def containers(self, filters: dict[str, str] | None = None, *args: Any, **kwargs: Any) -> Any:
        if filters is not None:
            if 'existing' in filters.get('name', ''):
                self.create_container(image='busybox:latest', name="buildbot-existing-87de7e")
                self.create_container(image='busybox:latest', name="buildbot-existing-87de7ef")

            return [c for c in self._containers.values() if c['name'].startswith(filters['name'])]
        return self._containers.values()

    def create_host_config(self, *args: Any, **kwargs: Any) -> None:
        self.call_args_create_host_config.append(kwargs)

    def create_container(self, image: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        self.call_args_create_container.append(kwargs)
        name: str | None = kwargs.get('name', None)
        if 'buggy' in image:
            raise RuntimeError('we could not create this container')
        for c in self._containers.values():
            if c['name'] == name:
                raise RuntimeError('cannot create with same name')
        ret: dict[str, Any] = {
            'Id': '8a61192da2b3bb2d922875585e29b74ec0dc4e0117fcbf84c962204e97564cd7',
            'Warnings': None,
        }
        self._containers[ret['Id']] = {
            'started': False,
            'image': image,
            'Id': ret['Id'],
            'name': name,  # docker does not return this
            'Names': ["/" + name],  # type: ignore[operator]  # this what docker returns
            "State": "running",
        }
        return ret

    def remove_container(self, id: str, **kwargs: Any) -> None:
        del self._containers[id]

    def logs(self, id: str, tail: int | None = None) -> bytes:
        return f"log for {id}\n1\n2\n3\nend\n".encode()

    def close(self) -> None:
        # dummy close, no connection to cleanup
        pass


class APIClient(Client):
    pass


class errors:
    class APIError(Exception):
        pass

    class NotFound(Exception):
        pass
