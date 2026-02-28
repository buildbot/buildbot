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
from typing import ClassVar
from typing import NamedTuple

from zope.interface import implementer

from buildbot.interfaces import IMaybeRenderableType
from buildbot.interfaces import IRenderable
from buildbot.util import ComparableMixin
from buildbot.util.twisted import async_to_deferred

if TYPE_CHECKING:
    from collections.abc import Sequence

    from buildbot.interfaces import IProperties


@implementer(IRenderable)
class GitCredentialInputRenderer(ComparableMixin):
    compare_attrs: ClassVar[Sequence[str]] = ('_credential_attributes',)

    def __init__(self, **credential_attributes: IMaybeRenderableType[str]) -> None:
        self._credential_attributes: dict[str, IMaybeRenderableType[str]] = credential_attributes

    @async_to_deferred
    async def getRenderingFor(self, build: IProperties) -> str:
        props = build.getProperties()

        rendered_attributes = []

        attributes = list(self._credential_attributes.items())

        # git-credential-approve parsing of the `url` attribute
        # will reset all other fields
        # So make sure it's the first attribute in the form
        if 'url' in self._credential_attributes:
            attributes.sort(key=lambda e: e[0] != "url")

        for key, value in attributes:
            rendered_value = await props.render(value)
            if rendered_value is not None:
                rendered_attributes.append(f"{key}={rendered_value}\n")

        return "".join(rendered_attributes)


class GitCredentialOptions(NamedTuple):
    # Each element of `credentials` should be a `str` which is a input format for git-credential
    # ref: https://git-scm.com/docs/git-credential#IOFMT
    credentials: list[IMaybeRenderableType[str]]
    # value to set the git config `credential.useHttpPath` to.
    # ref: https://git-scm.com/docs/gitcredentials#Documentation/gitcredentials.txt-useHttpPath
    use_http_path: bool | None = None


def add_user_password_to_credentials(
    auth_credentials: tuple[IMaybeRenderableType[str], IMaybeRenderableType[str]],
    url: IMaybeRenderableType[str] | None,
    credential_options: GitCredentialOptions | None,
) -> GitCredentialOptions:
    if credential_options is None:
        credential_options = GitCredentialOptions(credentials=[])
    else:
        # create a new instance to avoid side-effects
        credential_options = GitCredentialOptions(
            credentials=credential_options.credentials[:],
            use_http_path=credential_options.use_http_path,
        )

    username, password = auth_credentials
    credential_kwargs = {
        "username": username,
        "password": password,
    }
    if url is not None:
        credential_kwargs["url"] = url
    credential_options.credentials.insert(0, GitCredentialInputRenderer(**credential_kwargs))

    return credential_options
