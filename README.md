# NYX

![badge](https://img.shields.io/badge/made%20with-vuejs-blue.svg?style=flat-square)
![badge](https://img.shields.io/badge/made%20with-python-blue.svg?style=flat-square)
![badge](https://img.shields.io/github/last-commit/snuids/nyx)

NYX is a platform that can be used to digitize your organization. 
It is modular, highly customizable, scalable and allows to focus on functionnality rather than infrastructure. 

NYX is based on micro-services [Docker](https://www.docker.com/why-docker) and can be deployed on-premise or on your favorite cloud provider.

![Radar](https://raw.githubusercontent.com/snuids/nyx/master/medias/overview.gif)

## Summary

- [2 embedded Databases](#2-embedded-databases)
- [Based on Open source projects](#based-on-open-source-projects)
- [NYX is split in 3 parts](#based-on-open-source-projects)
  - [NYX_UI](https://github.com/snuids/nyx_ui)
  - [NYX_REST](https://github.com/snuids/nyx_rest)
  - [NYX_CONTAINERS](https://github.com/snuids/nyx_containers)
- [Additional repositories](#additional-reporsitories)
  - [NYX_WS_SERVER](https://github.com/snuids/nyx_ws_server)
- [Getting Started](#getting-started)
  - [Using the AWS AMI](#using-the-aws-ami)
  - [Running the platform locally](running_locally.md)
- [Architecture](folder_contents.md)

## 2 embedded databases:

- PostgreSQL. A SQL relational database to store Data that need strong consistency.
- Elasticsearch. A NoSQL distributed RESTful Database that allow you to process heavy analytics tasks.

## Based on Open source projects:

* Apache ActiveMQ a state of the art message broker with [online monitoring tools](https://github.com/snuids/AMQC).
* Apache Camel a Java framework that focuses on making integrations easier
and more accessible to developers (https://dzone.com/articles/open-source-integration-apache).
* Node-RED a graphical and programming tool to wire together hardware
devices, APIs and services.
* Jupyter Notebook one of the Data scientist essential tool.
* Vega, a visualization grammar, a declarative language for creative interactive
visualization designs.
* Kibana the window into your Elastic Stack that lets you visualize your
Elasticsearch data.


## NYX is split in 3 parts:

* [NYX_UI](https://github.com/snuids/nyx_ui) the web interface. You can add your specific interfaces in there to
increase the End User Experience.
* [NYX_REST](https://github.com/snuids/nyx_rest)  the REST API where you can add your specific functions to
interact with the both Databases.
* [NYX_CONTAINERS](https://github.com/snuids/nyx_containers) where you can ship your containers to insert, clean and
process your Data.


## Additional Repositories:

* [NYX_WS_SERVER](https://github.com/snuids/nyx_ws_server) dispatches stomp ActiveMQ messages to web sockets

# Getting Started

## Using the AWS AMI

The AMI is availabe in the Paris region.

## Running the platform locally

[Running Locally](running_locally.md)

# Architecture

[Folder Structure](folder_contents.md)
