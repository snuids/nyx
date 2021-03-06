[Back](README.md)

# NYX Folder Contents
```bash
├── ELK
│   ├── esnode1
│   │   └── conf
│   │       ├── elasticsearch.yml
│   │       └── jvm.options
│   ├── esnode2
│   │   └── conf
│   │       ├── elasticsearch.yml
│   │       └── jvm.options
│   └── esnodebal
│       ├── conf
│       │   ├── elasticsearch.yml
│       │   └── jvm.options
│       └── data
├── camelworkers
│   └── camelworker1
│       ├── config.xml
│       └── log4j.xml
├── certs
│   ├── nyx.crt
│   └── nyx.key
├── curator
│   ├── action_file.yml
│   └── curator_config.yml
├── docker-compose
│   └── docker-compose.yml
├── elastalert
│   ├── config.yaml
│   └── rules
│       └── CheckAMQ.yml
├── kibana
│   ├── kibanaclassic.yml
│   └── kibananyx.yml
├── logstash
│   └── config
├── nginx
│   ├── default.conf
├── reportrunner
│   ├── jasper
│   │   ├── myjasper.jasper
│   │   └── myjasper.jrxml
│   └── pythondef
└── sqlopendistro
    
```

# ./ELK
## ./ELK/esnode*: 
This folder contains the elastic search node configurations.

# ./camelworkers
## ./camelworkers/camelworker1: 
This folder contains the configguration file for the apache camel ETL system. The configuration is done via a xml file.
Additional workers can be added via the docker-compose file

# ./certs
This folder contains the private key and the certificate used by nginx to secure the system.

# ./curator
This folder contains the curator configuration file used to clean the system.

# ./docker-compose
This folder contains docker-compose.yml file that can be used to create all the containers.

# ./elastalert
This folder contains the Elast Alert system configuration file and rules

## ./elastalert/rules
This folder contains the Elast Alert rules.

# ./kibana
This folder contains two kibana yml files. One is used for the NYX integrated kibana. The other is used for the regular kibana.

# ./logstash
This folder contains the logstash configuration

# ./nginx
This folder contains the default.conf used by nginx to reverse proxy the various services of the platform.

# ./reportrunner
This folder contains the reports of the platform.

# ./sqlopendistro
This folder contains the Amazon Open Distro SQL jars. This folder is mounted in the esnodebal container.



















