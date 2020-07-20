# Troubleshooting
## Introduction

The nyx system uses docker as service manager. In order to behave properly, all the containers defined in the system must run.

## Checking docker

In order to interact with docker, the user must as root privileges.
An easy way to list the running containers is to use the following command:

> docker ps -a

This command should return a list of containers as shown below:

```
CONTAINER ID        IMAGE                                                 COMMAND                  CREATED             STATUS              PORTS                                                        
5a83d0733d03        snuids/nyx_restapi:v3.9.0                             "gunicorn -b 0.0.0.0…"   4 weeks ago         Up 4 weeks                                                                     
09e4ed1bd791        snuids/nyx_reportscheduler:v0.0.4                     "python nyx_reportsc…"   4 weeks ago         Up 4 weeks                                                                     
234a5102a3a4        snuids/nodered:v0.20.3-v10                            "npm start -- --user…"   4 weeks ago         Up 4 weeks          1880/tcp                                                   
da05596d3777        docker.elastic.co/elasticsearch/elasticsearch:6.5.4   "/usr/local/bin/dock…"   4 weeks ago         Up 4 weeks          9200/tcp, 9300/tcp                                         
533a68d2d69f        snuids/par_import_coswin:v0.0.8                       "python par_import_c…"   5 weeks ago         Up 5 weeks                                                                     
3994a7a1c75f        snuids/nyx_lambda:v1.5.2                              "python nyx_lambda.py"   2 months ago        Up 3 days                                                                        
830b7572bdbe        snuids/nyx_lambda:v1.5.2                              "python nyx_lambda.py"   2 months ago        Up 5 weeks                                                                       
ec4be44c06aa        snuids/nyx_ui:v3.24.0                                 "docker-entrypoint.s…"   2 months ago        Up 2 months                                                                    
47cd4afd2596        snuids/nyx_monitordocker:v1.0.5                       "python nyx_monitord…"   2 months ago        Up 5 weeks                                                                     
```

In order to list the containers that are not in the Up status, use the following command:

> docker ps -a | grep -v Up

This command should return an empty list.

### Restarting / Starting stopped containers

The easiest way of starting containers is to use the docker-compose command. It must be executed in the docker-compose folder of the nyx root installation folder.
It is possible to find the folder via the following commands:

> cd / ===> go to root directory
> find . -name "docker-compose.yml" ===> search recursively the file docker-compose.yml

'''
[root@ip-10-10-251-142 ~]# cd /
[root@ip-10-10-251-142 /]# find . -name "docker-compose.yml"
find: './proc/699/task/996/fd/424': No such file or directory
./home/nyx/docker-compose/docker-compose.yml
./home/nyx/backup/tempzip/docker-compose/docker-compose.yml
'''

In this installation two files where found. The good one is of course the first one because it is not in the backup folder.

You can the move to the appropriate directory using the command:

> cd /home/nyx/docker-compose/ =====> Depends on the following result

Issue then the following command to restart the stopped containers.

> docker-compose up -d

'''
[root@ip-10-10-251-142 /]# cd ./home/nyx/docker-compose/
[root@ip-10-10-251-142 docker-compose]# docker-compose up -d
redis is up-to-date
par_import_kizeo is up-to-date
openvpn is up-to-date
nyx_restapi is up-to-date
anacondab is up-to-date
nyx_reportscheduler is up-to-date
cerebro is up-to-date
esnode1 is up-to-date
nodered is up-to-date
portainer is up-to-date
camelworker1 is up-to-date
nyx_ui is up-to-date
logioweb is up-to-date
nyx_monitor_docker is up-to-date
nyx_xlsimporter is up-to-date
logstash is up-to-date
monitordocker is up-to-date
elastalert is up-to-date
kibananyx is up-to-date
esnode2 is up-to-date
nyx_rest_helper is up-to-date
nyx_formatconverter is up-to-date
kibana is up-to-date
nyx_lambda_3 is up-to-date
nyx_lambda_2 is up-to-date
postgres is up-to-date
curator is up-to-date
amqc is up-to-date
nyx_ws_server is up-to-date
nyx_mobile is up-to-date
nyx_reportrunner_1 is up-to-date
par_import_coswin is up-to-date
esnodebal is up-to-date
harvester is up-to-date
nginx is up-to-date
'''

