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




