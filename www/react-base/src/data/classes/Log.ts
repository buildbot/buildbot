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