/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {describe, expect, it, vi} from "vitest";
import {Stream} from "./Stream";

describe('Stream', () => {
  it('should add the listener to listeners on subscribe call', () => {
    const stream = new Stream();
    expect(stream.listeners.length).toBe(0);

    stream.subscribe(() => {});
    expect(stream.listeners.length).toBe(1);
  });


  it('should return the unsubscribe function on subscribe call', () => {
    const stream = new Stream();
    const listener = () => {};
    const otherListener = () => {};

    const unsubscribe = stream.subscribe(listener);
    stream.subscribe(otherListener);
    expect(stream.listeners).toContain(listener);

    unsubscribe();
    expect(stream.listeners).not.toContain(listener);
    expect(stream.listeners).toContain(otherListener);
  });

  it('should call all listeners on push call', () => {
    const stream = new Stream();

    const data = {a: 'A', b: 'B'};
    const listeners = {
      first(data: any) { expect(data).toEqual({a: 'A', b: 'B'}); },
      second(data: any) { expect(data).toEqual({a: 'A', b: 'B'}); }
    };

    vi.spyOn(listeners, 'first');
    vi.spyOn(listeners, 'second');

    stream.subscribe(listeners.first);
    stream.subscribe(listeners.second);

    expect(listeners.first).not.toHaveBeenCalled();
    expect(listeners.second).not.toHaveBeenCalled();

    stream.push(data);

    expect(listeners.first).toHaveBeenCalled();
    expect(listeners.second).toHaveBeenCalled();
  });

  it('should remove all listeners on destroy call', () => {
    const stream = new Stream();
    expect(stream.listeners.length).toBe(0);

    stream.subscribe(() => {});
    stream.subscribe(() => {});
    expect(stream.listeners.length).not.toBe(0);

    stream.destroy();
    expect(stream.listeners.length).toBe(0);
  });
});
