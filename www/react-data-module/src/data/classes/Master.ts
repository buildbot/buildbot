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

export class Master extends BaseClass {
  masterid!: number;
  active!: boolean;
  last_active!: number|null;
  name!: string;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.masterid));
    this.update(object);
  }

  update(object: any) {
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
