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
import {Button, Form, Modal} from "react-bootstrap";
import {Worker} from "buildbot-data-js";

type MultipleWorkersActionsModalProps = {
  workers: Worker[];
  preselectedWorkers: Worker[];
  onClose: () => void;
}

export const MultipleWorkersActionsModal = observer(({workers, preselectedWorkers, onClose}: MultipleWorkersActionsModalProps) => {
  if (workers.length === 1) {
    preselectedWorkers = [...workers];
  }

  const [errors, setErrors] = useState<string|null>(null);
  const [reasonText, setReasonText] = useState<string>("");
  const [selectedWorkerNames, setSelectedWorkerNames] = useState<string[]>(preselectedWorkers.map(w => w.name));

  const selectedWorkers = workers.filter(w => selectedWorkerNames.includes(w.name))
  const stopDisabled = selectedWorkers.length <= 0 || selectedWorkers.every(w => w.connected_to.length === 0)
  const pauseDisabled = selectedWorkers.length <= 0 || selectedWorkers.every(w => w.paused)
  const unpauseDisabled = selectedWorkers.length <= 0 || selectedWorkers.every(w => !w.paused)

  const doAction = async (method: string) => {
    if (selectedWorkers.length <= 0) {
      setErrors("No worker selected for action");
      return
    }
    setErrors(null);
    const results = await Promise.allSettled(selectedWorkers.map(w => w.control(method, {reason: reasonText})));
    const rejectedActions = results.filter(r => r.status === "rejected")
    if (rejectedActions.length > 0) {
      setErrors(rejectedActions.map(r => (r as PromiseRejectedResult).reason).join("\n"));
    }
    else {
      onClose();
    }
  }

  return (
    <Modal size="lg" show={true} onHide={() => onClose()}>
      <Modal.Header closeButton>
        <Modal.Title>Worker actions for {workers.length === 1 ? workers[0].name : "..."}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <div className="form-horizontal">
          {
            errors === null
              ? <></>
              : <div ng-show="error" className="alert alert-danger">{errors}</div>
          }
          {workers.length !== 1 ?
            <Form.Control
                as="select" multiple value={selectedWorkerNames}
                onChange={(event: React.ChangeEvent<HTMLSelectElement>) => {
                  const selectedOptions: HTMLOptionElement[] = [].slice.call(event.target.selectedOptions ?? []);
                  setSelectedWorkerNames(selectedOptions.map(e => e.value));
                }}>
              {workers.map(worker => (<option key={worker.name}>{worker.name}</option>))}
            </Form.Control>
            : <></>
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
        <Button variant="primary" disabled={stopDisabled} onClick={async () => await doAction('stop')}>
          Graceful Shutdown
        </Button>
        <Button variant="primary" disabled={stopDisabled} onClick={async () => await doAction('kill')}>
          Force Shutdown
        </Button>
        <Button variant="primary" disabled={pauseDisabled} onClick={async () => await doAction('pause')}>
          Pause
        </Button>
        <Button variant="primary" disabled={unpauseDisabled} onClick={async () => await doAction('unpause')}>
          Unpause
        </Button>
      </Modal.Footer>
    </Modal>
  )
});
