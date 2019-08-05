# NYX

NYX is an open source platform that can be used to digitize your Business. 
It is modular, highly customizable, scalable, in order to answer your business needs. 

NYX is based on micro-services (Docker) and can be deployed on-premise or on your favorite cloud provider.
It allows Business people to focus on how to solve business problems without having to worry about IT.

NYX embed 2 Databases:
* POSTGRESQL. An SQL relational Database to store your Data that need
strong consistency.
* ELASTICSEARCH. A NoSQL distributed RESTful Database that allow you to
process strong analytics tasks.

NYX integrate several Open Source Projects:
* Apache ActiveMQ a strongx message broker.
* Apache Camel a Java framework that focuses on making integrations easier
and more accessible to developers (https://dzone.com/articles/open-source-
integration-apache).
* Node-RED a graphical and programming tool to wire together hardware
devices, APIs and services.
* Jupyter Notebook one of the Data scientist essential tool.
* Vega, a visualization grammar, a declarative language for creative interactive
visualization designs.
* Kibana the window into your Elastic Stack that lets you visualize your
Elasticsearch data.

NYX is separated in 3 main parts:
* NYX_UI the web interface. You can add your specific interfaces in there to
increase the End User Experience. -&gt; link vers GITHUB
* NYX_REST the REST API where you can add your specific functions to
interact with the both Databases. -&gt; link vers GITHUB
* NYX_MODULES where you can ship your containers to insert, clean and
process your Data.

![Radar](https://raw.githubusercontent.com/snuids/nyx/master/medias/Untitled.gif)

# Getting Started

## Using the AWS AMI

The AMI is availabe in the Paris region.

## Running the platform locally

[Running Locally](running_locally.md)

# Architecture

[Folder Structure](folder_contents.md)
