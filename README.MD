# Installation Notes
## WTF?! My cronjob doesn't run?!
We can look here (https://stackoverflow.com/questions/22743548/cronjob-not-running) for troubleshooting help.
## FreeBSD Jail preparations
Access to USB devices. Need to be root for code to work. Need to solve for user. 
```shell
devfs rule -s 10 add path 'cua*' mode 0660 group 8123 unhide

# Use iocage to manage your jails
iocage set devfs_ruleset=10 inverters
iocage restart inverters
```
## Virtual Environment Prerequisites
Please add Wheel to the requirements file.
## Virtual Environment Activation
On FreeBSD the C Shell seems to be common.
```shell
source venv/bin/activate.csh
```
## Configuration File Requirements (.env) 
```dotenv
# Application Level
# Required Environment Variables
BYTE_ORDER="big"
PID_NAME="<your-pid-file-location>"
NEWLINE="\n"
COLUMN_SEPARATOR="|"
LIST_SEPARATOR=","

# Database Level
# Optional Environment Variables
DB_HOST="<host>"
DB_PORT="<port>"
DB_DATABASE="<database>"
DB_USER="<user>"
DB_PASSWORD="<password>"
```
