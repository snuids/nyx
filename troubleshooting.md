# Troubleshooting
## Introduction

The nyx system uses docker as service manager. In order to behave properly, all the containers defined in the system must run.

## Checking docker

In order to interact with docker, the user must as root privileges.
An easy way to list the running containers is to use the following command:

> docker ps -a

This command should return a list of containers as shown below:

> a
> b
