# NYX

<img src="https://img.shields.io/badge/made%20with-python-blue.svg?style=flat-square" alt="made with python">


NYX is an open source platform that can be used to digitize your Business. 
It is modular, highly customizable, scalable, in order to answer your business needs. 

NYX is based on micro-services (Docker) and can be deployed on-premise or on your favorite cloud provider.
It allows Business people to focus on how to solve business problems without having to worry about IT.

**NYX embed 2 Databases:**

- POSTGRESQL. A SQL relational database to store Data that need strong consistency.
- ELASTICSEARCH. A NoSQL distributed RESTful Database that allow you to process heavy analytics tasks.

**NYX integrate several Open Source Projects such as:**

* Apache ActiveMQ a state of the art message broker with online monitoring tools (https://github.com/snuids/AMQC).
* Apache Camel a Java framework that focuses on making integrations easier
and more accessible to developers (https://dzone.com/articles/open-source-integration-apache).
* Node-RED a graphical and programming tool to wire together hardware
devices, APIs and services.
* Jupyter Notebook one of the Data scientist essential tool.
* Vega, a visualization grammar, a declarative language for creative interactive
visualization designs.
* Kibana the window into your Elastic Stack that lets you visualize your
Elasticsearch data.

**NYX is split in 3 parts:**

* NYX_UI (https://github.com/snuids/nyx_ui) the web interface. You can add your specific interfaces in there to
increase the End User Experience. -&gt; link vers GITHUB
* NYX_REST (https://github.com/snuids/nyx_rest)  the REST API where you can add your specific functions to
interact with the both Databases. -&gt; link vers GITHUB
* NYX_CONTAINERS (https://github.com/snuids/nyx_containers) where you can ship your containers to insert, clean and
process your Data.

![Radar](https://raw.githubusercontent.com/snuids/nyx/master/medias/Untitled.gif)

** Additional Repositories:**

* NYX_WS_SERVER (https://github.com/snuids/nyx_ws_server) dispatches stomp ActiveMQ messages to web sockets

# Getting Started

## Using the AWS AMI

The AMI is availabe in the Paris region.

## Running the platform locally

[Running Locally](running_locally.md)

# Architecture

[Folder Structure](folder_contents.md)
