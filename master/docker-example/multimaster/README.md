This docker-compose environment show how to setup a buildbot in multimaster mode with docker and ha-proxy


The network schema is as follow:


           [ web users]
                |  |
    ------------------------
    [workers]   | /
         \|     |/
       [  HAPROXY  ]
         /     \
        /       \
    [master1]..[masterN]
          |  \    / |
          |   \ /   |
          |   /\    |
    [ postgre]  [crossbar]


The same haproxy serves as load balancing for both web and worker protocols

You can run this by using for example 4 masters

    docker-compose up -d
    docker-compose scale buildbot=4
