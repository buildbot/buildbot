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

    jest.spyOn(listeners, 'first');
    jest.spyOn(listeners, 'second');

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
