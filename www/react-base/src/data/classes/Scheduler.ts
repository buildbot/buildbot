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

import BaseClass from "./BaseClass";
import IDataDescriptor from "./DataDescriptor";
import {IDataAccessor} from "../DataAccessor";
import {RequestQuery} from "../DataQuery";

export type SchedulerMaster = {
  masterid: number;
  active: boolean;
  last_active: number|null;
  name: string;
}

export class Scheduler extends BaseClass {
  schedulerid!: number;
  name!: string;
  master!: SchedulerMaster | null;
  enabled!: boolean;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.schedulerid));
    this.update(object);
  }

  update(object: any) {
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
