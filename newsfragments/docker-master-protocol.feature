Added support for specifying the master protocol to ``DockerLatentWorker`` and
``KubeLatentWorker``. These classes get new ``master_protocol`` argument. The worker
docker image will receive the master protocol via BUILDMASTER_PROTOCOL environment
variable.
