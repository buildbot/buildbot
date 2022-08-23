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

export class Changesource extends BaseClass {
  changesourceid!: number;
  master!: any; // FIXME
  name!: string;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.changesourceid));
    this.update(object);
  }

  update(object: any) {
    this.changesourceid = object.changesourceid;
    this.master = object.master;
    this.name = object.name;
  }

  toObject() {
    return {
      changesourceid: this.changesourceid,
      master: this.master,
      name: this.name,
    };
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get<Changesource>("changesources", query, changesourceDescriptor);
  }
}

export class ChangesourceDescriptor implements IDataDescriptor<Changesource> {
  restArrayField = "changesources";
  fieldId: string = "changesourceid";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new Changesource(accessor, endpoint, object);
  }
}

export const changesourceDescriptor = new ChangesourceDescriptor();
