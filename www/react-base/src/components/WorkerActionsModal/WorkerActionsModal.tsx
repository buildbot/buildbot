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

import {observer} from "mobx-react";
import {useState} from "react";
import {Button, Modal} from "react-bootstrap";
import {Worker} from "../../data/classes/Worker";

type WorkerActionsModalProps = {
  worker: Worker;
  onClose: () => void;
}

const WorkerActionsModal = observer(({worker, onClose}: WorkerActionsModalProps) => {

  const [errors, setErrors] = useState<string|null>(null);
  const [reasonText, setReasonText] = useState<string>("");

  const doAction = (method: string) => {
    const doActionAsync = async () => {
      try {
        await worker.control(method, {reason: reasonText});
        onClose();
      } catch (err: any) {
        setErrors(err.message);
      }
    }
    doActionAsync();
  }

  const stopDisabled = worker.connected_to.length === 0;

  return (
    <Modal show={true} onHide={() => onClose()}>
      <Modal.Header closeButton>
        <Modal.Title>Worker actions for {worker.name}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <div className="form-horizontal">
          {
            errors === null
              ? <></>
              : <div ng-show="error" className="alert alert-danger">{errors}</div>
          }
          <label htmlFor="reason" className="control-label col-sm-2">Reason</label>
          <div className="col-sm-10">
            <textarea rows={15} value={reasonText} onChange={e => setReasonText(e.target.value)}
                      className="form-control"/>
          </div>
        </div>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="default" onClick={() => onClose()}>Cancel</Button>
        <Button variant="primary" disabled={stopDisabled} onClick={() => doAction('stop')}>
          Graceful Shutdown
        </Button>
        <Button variant="primary" disabled={stopDisabled} onClick={() => doAction('kill')}>
          Force Shutdown
        </Button>
        <Button variant="primary" disabled={worker.paused} onClick={() => doAction('pause')}>
          Pause
        </Button>
        <Button variant="primary" disabled={!worker.paused} onClick={() => doAction('unpause')}>
          Unpause
        </Button>
      </Modal.Footer>
    </Modal>
  )
});

export default WorkerActionsModal;
