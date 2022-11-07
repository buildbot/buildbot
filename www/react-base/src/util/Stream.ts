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

export type StreamListener<T> = (data: T) => void;

export class Stream<T> {
  lastId: number = 0;
  listeners: StreamListener<T>[] = [];

  subscribe(listener: StreamListener<T>) {

    this.listeners.push(listener);

    // unsubscribe
    return () => {
      const i = this.listeners.indexOf(listener);
      this.listeners.splice(i, 1);
    };
  }

  push(data: T) {
    for (let listener of this.listeners) {
      listener(data);
    }
  }

  destroy() {
    // we need to keep reference to listeners array
    while (this.listeners.length > 0) {
      this.listeners.pop();
    }
  }

  private generateId() {
    return this.lastId++;
  }
}