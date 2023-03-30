/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

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
