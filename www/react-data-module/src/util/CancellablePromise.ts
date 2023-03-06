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

export class CancellablePromise<T> extends Promise<T> {
  private onCancel: (() => void) | null;

  constructor(executor: (
      resolve: (value: T | PromiseLike<T>) => void,
      reject: (reason?: any) => void,
      onCancel: (cancelCallback: () => void) => void) => void) {
    let onCancel: (() => void) | null = null;
    super((resolve, reject) => executor(resolve, reject,
      (callback: () => void) => onCancel = callback));
    this.onCancel = onCancel;
  }

  public cancel() {
    if (this.onCancel !== null) {
      this.onCancel();
    }
  }
}