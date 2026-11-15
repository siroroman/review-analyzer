import base64
import json
import re
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import SecretStr

from app.queue._types import QueueError
from app.transport import HttpError, HttpRequest, HttpTransport

_NAME = re.compile(r"[A-Za-z0-9_-]{1,400}")
_ALREADY_EXISTS = 409


@dataclass(frozen=True)
class CloudTasksConfig:
    """Where tasks go: one Cloud Tasks queue, pushing to the worker's URL as `service_account`."""

    project: str
    location: str
    queue: str
    worker_url: str
    service_account: str
    timeout: float = 10.0


class CloudTasksQueue:
    """`Queue` over the Cloud Tasks REST API.

    The task name is derived from the Run id, so enqueueing a Run twice creates one task: Cloud Tasks
    answers 409 for the second and that is a success here. `access_token` is called per request, so a
    short-lived token can be refreshed by whoever supplies it.
    """

    def __init__(
        self, config: CloudTasksConfig, transport: HttpTransport, access_token: Callable[[], SecretStr]
    ) -> None:
        self._config = config
        self._transport = transport
        self._access_token = access_token

    def enqueue(self, run_id: str) -> None:
        if not _NAME.fullmatch(run_id):
            raise QueueError("the Run id cannot be a task name")
        config = self._config
        parent = f"projects/{config.project}/locations/{config.location}/queues/{config.queue}"
        body = json.dumps({"run_id": run_id}).encode()
        task = {
            "name": f"{parent}/tasks/run-{run_id}",
            "httpRequest": {
                "url": config.worker_url,
                "httpMethod": "POST",
                "headers": {"Content-Type": "application/json"},
                "body": base64.b64encode(body).decode(),
                "oidcToken": {"serviceAccountEmail": config.service_account},
            },
        }
        request = HttpRequest(
            method="POST",
            url=f"https://cloudtasks.googleapis.com/v2/{parent}/tasks",
            headers={
                "Authorization": f"Bearer {self._access_token().get_secret_value()}",
                "Content-Type": "application/json",
            },
            body=json.dumps({"task": task}).encode(),
            timeout=config.timeout,
        )
        try:
            response = self._transport.send(request)
        except HttpError as error:
            raise QueueError("Cloud Tasks gave no answer") from error
        if response.status != _ALREADY_EXISTS and not 200 <= response.status < 300:
            raise QueueError(f"Cloud Tasks refused the task: HTTP {response.status}")
