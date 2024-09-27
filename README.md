A script to help with running multiple services locally

## Usage

Run all services:
```shell
./startup.py
```

Run all services except a specified list:
```shell
./startup.py -e/--except [comma separated list of services to exclude]
```

Run only specified services:
```shell
./startup.py -o/--only [comma separated list of services to run]
```


## Configuration

The script is configured in the `test-conf.yaml` file
This file lists the different services along with their working directories, startup commands, teardown commands, and any pre-startup requirements.

#### Format:
```yaml
services:
  service-name:
    path: ../working-dir-for-service
    startup:
      - ./startup.sh
    pre-startup: # [OPTIONAL] pre-startup commands
      # only run if --pre is passed to the script
      - ./load-dummy-data.sh
    teardown:
      # [OPTIONAL] commands to run on Ctrl+C, e.g. docker compose down
      - ./teardown.sh
```
The yaml is made up of a top level `services`, with a list of named services under that.

Each service defines:
- `path`: path to run commands from (relative to `service-runner` location)
- `startup`: list of startup commands to run every time the service is spun up
- [OPTIONAL] `pre-startup`: list of commands to run prior to startup, only run if `--pre` is passed
- [OPTIONAL] `teardown`: list of commands to run every time the services is stopped