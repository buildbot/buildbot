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

export class Log extends BaseClass {
  @observable logid!: number;
  @observable complete!: boolean;
  @observable name!: string;
  @observable num_lines!: number;
  @observable slug!: string;
  @observable stepid!: number;
  @observable type!: string;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.logid));
    this.update(object);
    makeObservable(this);
  }

  @action update(object: any) {
    this.logid = object.logid;
    this.complete = object.complete;
    this.name = object.name;
    this.num_lines = object.num_lines;
    this.slug = object.slug;
    this.stepid = object.stepid;
    this.type = object.type;
  }

  toObject() {
    return {
      logid: this.logid,
      complete: this.complete,
      name: this.name,
      num_lines: this.num_lines,
      slug: this.slug,
      stepid: this.stepid,
      type: this.type,
    };
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get<Log>("logs", query, logDescriptor);
  }
}

export class LogDescriptor implements IDataDescriptor<Log> {
  restArrayField = "logs";
  fieldId: string = "logid";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new Log(accessor, endpoint, object);
  }
}

export const logDescriptor = new LogDescriptor();
