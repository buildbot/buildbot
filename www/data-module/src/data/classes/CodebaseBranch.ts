/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {action, makeObservable, observable} from "mobx";
import {BaseClass} from "./BaseClass";
import {IDataDescriptor} from "./DataDescriptor";
import {IDataAccessor} from "../DataAccessor";

export class CodebaseBranch extends BaseClass {
  @observable branchid!: number;
  @observable codebaseid!: number;
  @observable name!: string;
  @observable commitid!: number;
  @observable last_timestamp!: number;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.branchid));
    this.update(object);
    makeObservable(this);
  }

  @action update(object: any) {
    this.branchid = object.branchid;
    this.codebaseid = object.codebaseid;
    this.name = object.name;
    this.commitid = object.commitid;
    this.last_timestamp = object.last_timestamp;
  }

  toObject() {
    return {
      branchid: this.branchid,
      codebaseid: this.codebaseid,
      name: this.name,
      commitid: this.commitid,
      last_timestamp: this.last_timestamp,
    };
  }

}

export class CodebaseBranchDescriptor implements IDataDescriptor<CodebaseBranch> {
  restArrayField = "branches";
  fieldId: string = "branchid";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new CodebaseBranch(accessor, endpoint, object);
  }
}

export const codebaseBranchDescriptor = new CodebaseBranchDescriptor();
