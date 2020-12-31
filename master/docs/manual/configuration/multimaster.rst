.. _Multimaster:

Multimaster
-----------

.. Warning::

    Buildbot Multimaster is considered experimental.
    There are still some companies using it in production.
    Don't hesitate to use the mailing lists to share your experience.

.. blockdiag::

    blockdiag multimaster {
       Worker1 -> LoadBalancer -> Master1 -> database
       Worker2 -> LoadBalancer
       Worker2 [shape = "dots"];
       WorkerN -> LoadBalancer -> Master2 -> database
       User1 -> LoadBalancerUI -> MasterUI1 -> database
       User2 -> LoadBalancerUI -> MasterUI2 -> database
       Master1 -> crossbar.io
       Master2 -> crossbar.io
       MasterUI1 -> crossbar.io
       MasterUI2 -> crossbar.io
       database [shape = "flowchart.database", stacked];
       LoadBalancerUI [shape = ellipse];
       LoadBalancer [shape = ellipse];
       crossbar.io [shape = mail];
       User1 [shape = actor];
       User2 [shape = actor];
       default_shape = roundedbox;
       default_node_color = "#33b5e5";
       default_group_color = "#428bca";
       default_linecolor = "#0099CC";
       default_textcolor = "#e1f5fe";
       group {
          shape = line;
          Worker1; Worker2; WorkerN
       }
       group {
          shape = line;
          Master1; Master2; MasterUI1; MasterUI2
       }
       group {
          shape = line;
          database; crossbar.io;
       }
       group {
          shape = line;
          User1; User2;
       }
    }

Buildbot supports interconnection of several masters.
This has to be done through a multi-master enabled message queue backend.
As of now the only one supported is wamp and crossbar.io.
see :ref:`wamp <MQ-Specification>`

There are then several strategy for introducing multimaster in your buildbot infra.
A simple way to say it is by adding the concept of symmetrics and asymmetrics multimaster (like there is SMP and AMP for multi core CPUs)

Symmetric multimaster is when each master share the exact same configuration. They run the same builders, same schedulers, same everything, the only difference is that workers are connected evenly between the masters (by any means (e.g. DNS load balancing, etc)) Symmetric multimaster is good to use to scale buildbot horizontally.

Asymmetric multimaster is when each master have different configuration. Each master may have a specific responsibility (e.g schedulers, set of builder, UI). This was more how you did in 0.8, also because of its own technical limitations. A nice feature of asymmetric multimaster is that you can have the UI only handled by some masters.

Separating the UI from the controlling will greatly help in the performance of the UI, because badly written BuildSteps?? can stall the reactor for several seconds.

The fanciest configuration would probably be a symmetric configuration for everything but the UI.
You would scale the number of UI master according to your number of UI users, and scale the number of engine masters to the number of workers.

Depending on your workload and size of master host, it is probably a good idea to start thinking of multimaster starting from a hundred workers connected.

Multimaster can also be used for high availability, and seamless upgrade of configuration code.
Complex configuration indeed requires sometimes to restart the master to reload custom steps or code, or just to upgrade the upstream buildbot version.

In this case, you will implement following procedure:

* Start new master(s) with new code and configuration.
* Send a graceful shutdown to the old master(s).
* New master(s) will start taking the new jobs, while old master(s) will just finish managing the running builds.
* As an old master is finishing the running builds, it will drop the connections from the workers, who will then reconnect automatically, and by the mean of load balancer will get connected to a new master to run new jobs.

As buildbot nine has been designed to allow such procedure, it has not been implemented in production yet as we know.
There is probably a new REST api needed in order to graceful shutdown a master, and the details of gracefully dropping the connection to the workers to be sorted out.
