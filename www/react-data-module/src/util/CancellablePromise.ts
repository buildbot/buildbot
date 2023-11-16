/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

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
