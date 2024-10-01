# Docker Volume Mappings Generator

Managing backups for Docker volumes can become cumbersome, especially when dealing with a large number of services and volumes. Manually updating `docker-compose.yml` files to include all the necessary volume mappings is error-prone and time-consuming.

The **Docker Volume Mappings Generator** is a script designed to automate the creation of Docker Compose volume mappings for backing up Docker named volumes and specified root directories. It simplifies the backup configuration process, ensuring that all relevant data is included without manual intervention.