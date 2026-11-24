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
import {Config} from 'buildbot-ui';
import {globalSettings} from './GlobalSettings';
import {initializeGlobalSetup} from './GlobalSetup';
import './ThemeManager';

describe('ThemeManager', () => {
  it('keeps Bootstrap color mode in sync with the appearance setting', () => {
    const root = document.documentElement;
    const originalAttributes = {
      style: root.getAttribute('style'),
      'data-bs-theme': root.getAttribute('data-bs-theme'),
    };

    try {
      initializeGlobalSetup({} as Config);
      expect(root.getAttribute('data-bs-theme')).toEqual('light');

      globalSettings.setSetting('Appearance.theme', 'Dark');
      expect(root.getAttribute('data-bs-theme')).toEqual('dark');

      globalSettings.setSetting('Appearance.theme', 'Light');
      expect(root.getAttribute('data-bs-theme')).toEqual('light');
    } finally {
      globalSettings.setSetting('Appearance.theme', 'Light');
      for (const [name, value] of Object.entries(originalAttributes)) {
        if (value === null) {
          root.removeAttribute(name);
        } else {
          root.setAttribute(name, value);
        }
      }
    }
  });
});
