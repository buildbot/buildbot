To test this container do following steps.

1. Configure master to expect worker::

       c['workers'] = [
           worker.Worker("docker-worker", "pass"),
       ]

2. Build container using::

       $ sudo docker build -t worker .

3. Run worker container. You need to specify how to connect to the master.

   If master is run locally with default port configuration you can run 
   container with host network::


       $ sudo docker run \
           -e WORKERNAME=docker-worker \
           -e WORKERPASS=pass \
           -e BUILDMASTER=localhost \
           -e BUILDMASTER_PORT=9989 \
           --net=host \
           worker
