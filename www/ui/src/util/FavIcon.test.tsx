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

import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {createRoot, Root} from 'react-dom/client';
import axios from 'axios';
import {UNKNOWN, SUCCESS} from 'buildbot-data-js';
import {Config, ConfigContext} from '../contexts/Config';
import {useFavIcon} from './FavIcon';

function TestFavIcon({result}: {result: number}) {
  useFavIcon(result);
  return null;
}

async function flushEffects() {
  await new Promise<void>((resolve) => {
    window.requestAnimationFrame(() => resolve());
  });
  await new Promise((resolve) => setTimeout(resolve, 0));
  await new Promise((resolve) => setTimeout(resolve, 0));
}

describe('FavIcon', () => {
  let iconElement: HTMLLinkElement;
  let container: HTMLDivElement;
  let root: Root;

  function makeConfig(overrides: Partial<Config> = {}): Config {
    return {
      title: 'Buildbot',
      titleURL: '',
      buildbotURL: 'http://localhost:8080/',
      multiMaster: false,
      ui_default_config: {},
      versions: [],
      auth: {name: '', oauth2: false, fa_icon: '', autologin: false},
      avatar_methods: [],
      plugins: {},
      user: {anonymous: true},
      user_any_access_allowed: false,
      project_widgets: [],
      port: '8080',
      ...overrides,
    };
  }

  beforeEach(() => {
    iconElement = document.createElement('link');
    iconElement.id = 'bbicon';
    document.head.appendChild(iconElement);
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  afterEach(() => {
    if (root) {
      root.unmount();
    }
    iconElement.remove();
    container.remove();
    vi.restoreAllMocks();
  });

  it('should not produce double slash in fallback icon URL', async () => {
    const config = makeConfig({buildbotURL: 'http://localhost:8080/'});

    root = createRoot(container);
    root.render(
      <ConfigContext.Provider value={config}>
        <TestFavIcon result={UNKNOWN} />
      </ConfigContext.Provider>,
    );
    await flushEffects();

    // When result is UNKNOWN, setFavIconUrlOriginal is called which sets icon.png
    const href = iconElement.getAttribute('href');
    expect(href).toContain('icon.png');
    expect(href).not.toContain('//icon');
  });

  it('should not produce double slash in SVG fetch URL', async () => {
    const getSpy = vi.spyOn(axios, 'get').mockResolvedValue({data: '<svg></svg>'});
    const config = makeConfig({buildbotURL: 'http://localhost:8080/'});

    root = createRoot(container);
    root.render(
      <ConfigContext.Provider value={config}>
        <TestFavIcon result={SUCCESS} />
      </ConfigContext.Provider>,
    );
    await flushEffects();

    expect(getSpy).toHaveBeenCalledWith('http://localhost:8080/icon.svg');
  });

  it('should use relative path when isProxy is true', async () => {
    const config = makeConfig({buildbotURL: 'http://localhost:8080/', isProxy: true});

    root = createRoot(container);
    root.render(
      <ConfigContext.Provider value={config}>
        <TestFavIcon result={UNKNOWN} />
      </ConfigContext.Provider>,
    );
    await flushEffects();

    // When isProxy is true, url becomes empty string ''
    // So href should be 'icon.png' (relative), not '/icon.png' (absolute)
    const href = iconElement.getAttribute('href');
    expect(href).toBe('icon.png');
  });
});
