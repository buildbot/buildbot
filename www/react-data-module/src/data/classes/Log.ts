/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {BaseClass} from "./BaseClass";
import {IDataDescriptor} from "./DataDescriptor";
import {IDataAccessor} from "../DataAccessor";
import {RequestQuery} from "../DataQuery";

export class Log extends BaseClass {
  logid!: number;
  complete!: boolean;
  name!: string;
  num_lines!: number;
  slug!: string;
  stepid!: number;
  type!: string;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.logid));
    this.update(object);
  }

  update(object: any) {
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
