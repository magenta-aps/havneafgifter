<!--
SPDX-FileCopyrightText: 2025 Magenta ApS <info@magenta.dk>

SPDX-License-Identifier: MPL-2.0
-->

# Talippoq (port taxes)

This repository contains the Talippoq application created by Magenta ApS for Naalakkersuisut, the
Government of Greenland. The application allows vessels to report their
arrival to Greenlandic harbours. The authorities can then collect the
corresponding charges depending on vessel type (cruise ship, passenger,
freighter, etc.).

## Running the app

You can run the app by running `docker compose up`

## Interacting with the app

The app runs on `localhost:8050`. Locally you can log in with username =
`admin` and password = `admin`.

More test users are available, please refer to the `CREATE_DUMMY_USERS`
section of the file `docker/entrypoint.sh`.

## Running the tests

You can run tests locally by using `docker exec`:

```
docker exec havneafgifter-web bash -c 'coverage run manage.py test --parallel ; coverage combine ; coverage report --show-missing'
```


## Licensing and copyright


Copyright (c) 2025, Magenta ApS.

The Talippoq (Port Taxes) system is free software and may be used, studied,
modified and shared under the terms of Mozilla Public License, version
2.0. A copy of the license text may be found in the LICENSE file.
