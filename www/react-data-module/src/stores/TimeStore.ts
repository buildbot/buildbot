/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {action, makeObservable, observable} from "mobx";
import moment from "moment";

export default class TimeStore {
  @observable now: number;

  constructor() {
    makeObservable(this);
    this.now = 0;
  }

  @action setTime(now: number) {
    this.now = now;
  }

  @action setTimeFromString(now: string) {
    this.now = moment(now).unix();
  }
}
