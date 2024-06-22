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

export type SchedulerMaster = {
  masterid: number;
  active: boolean;
  last_active: number|null;
  name: string;
}

export class Scheduler extends BaseClass {
  @observable schedulerid!: number;
  @observable name!: string;
  @observable master!: SchedulerMaster | null;
  @observable enabled!: boolean;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.schedulerid));
    this.update(object);
    makeObservable(this);
  }

  @action update(object: any) {
    this.schedulerid = object.schedulerid;
    this.name = object.name;
    this.master = object.master;
    this.enabled = object.enabled;
  }

  toObject() {
    return {
      schedulerid: this.schedulerid,
      name: this.name,
      master: this.master,
      enabled: this.enabled,
    };
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get<Scheduler>("schedulers", query, schedulerDescriptor);
  }
}

export class SchedulerDescriptor implements IDataDescriptor<Scheduler> {
  restArrayField = "schedulers";
  fieldId: string = "schedulerid";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new Scheduler(accessor, endpoint, object);
  }
}

export const schedulerDescriptor = new SchedulerDescriptor();
