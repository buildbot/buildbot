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

import {describe, expect, it} from 'vitest';
import {resolveDefaultPage} from './DefaultPage';

describe('resolveDefaultPage', () => {
  it('returns null when default_page is undefined', () => {
    expect(resolveDefaultPage(undefined)).toBeNull();
  });

  it('returns null when default_page is empty string', () => {
    expect(resolveDefaultPage('')).toBeNull();
  });

  it('returns null when default_page is whitespace only', () => {
    expect(resolveDefaultPage('   ')).toBeNull();
  });

  it('prepends slash when default_page has no leading slash', () => {
    expect(resolveDefaultPage('console')).toBe('/console');
  });

  it('keeps slash when default_page already has leading slash', () => {
    expect(resolveDefaultPage('/console')).toBe('/console');
  });

  it('returns null when default_page starts with //', () => {
    expect(resolveDefaultPage('//evil.com')).toBeNull();
  });

  it('returns null when default_page has a URI scheme', () => {
    expect(resolveDefaultPage('https://evil.com')).toBeNull();
  });

  it('returns null when default_page uses javascript protocol', () => {
    expect(resolveDefaultPage('javascript:alert(1)')).toBeNull();
  });

  it('allows paths containing a colon', () => {
    expect(resolveDefaultPage('builders/my-page:v2')).toBe('/builders/my-page:v2');
  });
});
