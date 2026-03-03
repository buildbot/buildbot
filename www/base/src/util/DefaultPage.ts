/*
  This file is part of Buildbot.  Buildbot is free software: you can
  redistribute it and/or modify it under the terms of the GNU General Public
  License as published by the Free Software Foundation, version 2.

  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
  FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
  details.

  You should have received a copy of the GNU General Public License along with
  this program; if not, write to the Free Software Foundation, Inc., 51
  Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

  Copyright Buildbot Team Members
*/

export function resolveDefaultPage(
  defaultPage: string | undefined,
  registeredRoutes: Iterable<string>,
): string | null {
  if (defaultPage === undefined || defaultPage.trim() === '') {
    return null;
  }

  const normalized = defaultPage.startsWith('/') ? defaultPage : `/${defaultPage}`;

  const routes = new Set(registeredRoutes);
  if (routes.has(normalized)) {
    return normalized;
  }

  console.warn(
    `default_page "${defaultPage}" does not match any registered route. Falling back to home page.`,
  );
  return null;
}
