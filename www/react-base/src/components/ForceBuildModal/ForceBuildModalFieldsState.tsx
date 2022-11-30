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

import {action, observable} from "mobx";

export class ForceBuildfieldsState {
  @observable value: string = '';
  @observable errors: string[] = [];

  constructor(value: string) {
    this.value = value;
  }
}

export class ForceBuildModalFieldsState {
  fields = observable.map<string, ForceBuildfieldsState>();

  setupField(name: string, defaultValue: string) {
    if (!this.fields.has(name)) {
      this.createNewField(name, defaultValue);
    }
  }

  @action createNewField(name: string, defaultValue: string) {
    this.fields.set(name, new ForceBuildfieldsState(defaultValue));
  }

  @action setValue(name: string, value: string) {
    const field = this.fields.get(name);
    if (field === undefined) {
      throw Error(`Field with name ${name} does not exist`)
    }
    field.value = value;
  }

  getValue(name: string): string | null {
    const field = this.fields.get(name);
    if (field === undefined) {
      return null;
    }
    return field.value;
  }

  @action clearErrors() {
    this.fields.forEach(e => { e.errors = []; });
  }

  @action addError(name: string, error: string) {
    const field = this.fields.get(name);
    if (field === undefined) {
      throw Error(`Filed with name ${name} does not exist`)
    }
    field.errors.push(error);
  }
}
