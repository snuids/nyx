[Back](README.md)

# Running Locally
In order to run the platform locally, you need:

* A linux based machine with at least 8GB of memory. 
* git installed
* docker installed
* docker-compose installed

## Step 1

* clone this repository
* navigate to the folder nyx/docker-compose using a shell
* type:
```shell
docker-compose up -d 
```

## Step 2

* cd your command line to the folder esnodebal
* type chmod ugo+rw -R *
* docker restart esnodebal
* check that esnodebal is running if not
** Type docker logs -f esnodebal
** if the error is 
*** use the following command to edit the file limits
```sudo vi /etc/security/limits.conf```



## Step 3

* Once all the containers up, use a browser to open the following URL:
