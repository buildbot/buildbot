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

import {describe, expect, it, vi} from 'vitest';
import {resolveDefaultPage} from './DefaultPage';

describe('resolveDefaultPage', () => {
  const routes = ['/console', '/waterfall', '/grid'];

  it('returns null when default_page is undefined', () => {
    expect(resolveDefaultPage(undefined, routes)).toBeNull();
  });

  it('returns null when default_page is empty string', () => {
    expect(resolveDefaultPage('', routes)).toBeNull();
  });

  it('returns null when default_page is whitespace only', () => {
    expect(resolveDefaultPage('   ', routes)).toBeNull();
  });

  it('returns matching route when default_page has no leading slash', () => {
    expect(resolveDefaultPage('console', routes)).toBe('/console');
  });

  it('returns matching route when default_page has leading slash', () => {
    expect(resolveDefaultPage('/console', routes)).toBe('/console');
  });

  it('returns null and warns when default_page does not match any route', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(resolveDefaultPage('nonexistent', routes)).toBeNull();
    expect(warnSpy).toHaveBeenCalledOnce();
    warnSpy.mockRestore();
  });
});
