/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {action, makeObservable, observable} from "mobx";
import {BaseClass} from "./BaseClass";
import {IDataDescriptor} from "./DataDescriptor";
import {IDataAccessor} from "../DataAccessor";
import {RequestQuery} from "../DataQuery";

export class Master extends BaseClass {
  @observable masterid!: number;
  @observable active!: boolean;
  @observable last_active!: number|null;
  @observable name!: string;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.masterid));
    this.update(object);
    makeObservable(this);
  }

  @action update(object: any) {
    this.masterid = object.masterid;
    this.active = object.active;
    this.last_active = object.last_active;
    this.name = object.name;
  }

  toObject() {
    return {
      masterid: this.masterid,
      active: this.active,
      last_active: this.last_active,
      name: this.name,
    };
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get<Master>("masters", query, masterDescriptor);
  }
}

export class MasterDescriptor implements IDataDescriptor<Master> {
  restArrayField = "masters";
  fieldId: string = "masterid";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new Master(accessor, endpoint, object);
  }
}

export const masterDescriptor = new MasterDescriptor();
