#!/bin/bash

# SPDX-FileCopyrightText: 2024 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0

set -e
MAKE_MIGRATIONS=${MAKE_MIGRATIONS:=false}
MIGRATE=${MIGRATE:=false}
TEST=${TEST:=false}
MAKEMESSAGES=${MAKEMESSAGES:=false}
COMPILEMESSAGES=${COMPILEMESSAGES:=false}
DJANGO_DEBUG=${DJANGO_DEBUG:=false}
LOAD_FIXTURES=${LOAD_FIXTURES:=false}
LOAD_DEMODATA=${LOAD_DEMODATA:=false}
CREATE_GROUPS=${CREATE_GROUPS:=false}
CREATE_DUMMY_ADMIN=${CREATE_DUMMY_ADMIN:=false}
CREATE_DUMMY_USERS=${CREATE_DUMMY_USERS:=false}
SKIP_IDP_METADATA=${SKIP_IDP_METADATA:=false}

python manage.py wait_for_db
python manage.py createcachetable

python manage.py collectstatic --no-input --clear
python manage.py compress --force

if [ "${MAKE_MIGRATIONS,,}" = true ]; then
  echo 'generating migrations'
  python manage.py makemigrations --no-input
fi
if [ "${MIGRATE,,}" = true ]; then
  echo 'running migrations'
  python manage.py migrate
fi

if [ "${LOAD_FIXTURES}" = true ]; then
  echo 'loading fixtures'
  python manage.py load_fixtures
fi

if [ "${LOAD_DEMODATA}" = true ]; then
  echo 'loading demodata'
  python manage.py load_demodata
fi

if [ "${CREATE_GROUPS}" = true ]; then
  echo 'creating groups'
  ./manage.py create_groups
fi

if [ "${CREATE_DUMMY_ADMIN}" = true ]; then
  echo 'creating superuser'
  ./manage.py createuser admin admin -sS
fi

if [ "${CREATE_DUMMY_USERS}" = true ]; then
  echo 'creating tax user'
  ./manage.py createuser tax tax -g TaxAuthority
  echo 'creating shipping user'
  ./manage.py createuser shipping shipping -g Shipping --shipping-agent Agenten
  echo 'creating ship user'
  ./manage.py createuser 9074729 ship -g Ship --email ship@ship.com
  echo 'creating portauthority admin user'
  ./manage.py createuser ral_admin ral_admin -g PortAuthority --port-authority Royal Arctic Line A/S --port-authority-admin --email ral-dummy-admin@test.ral
  echo 'creating portauthority user'
  ./manage.py createuser portauthority portauthority -g PortAuthority --port-authority Royal Arctic Line A/S
fi

python manage.py createcachetable
if [ "${SKIP_IDP_METADATA,,}" = false ]; then
  python manage.py update_mitid_idp_metadata
fi

if [ "${MAKEMESSAGES,,}" = true ]; then
  echo 'making messages'
  python manage.py make_messages --locale=en --locale=da --locale=kl --no-obsolete --add-location file --domain django
  python manage.py make_messages --locale=en --locale=da --locale=kl --no-obsolete --add-location file --domain djangojs
fi
if [ "${COMPILEMESSAGES,,}" = true ]; then
  echo 'compiling messages'
  python manage.py compilemessages --locale=en --locale=da --locale=kl --verbosity 0
fi
if [ "${TEST,,}" = true ]; then
  echo 'running tests'
  coverage run manage.py test --noinput
  coverage combine
  coverage report --show-missing
fi

exec "$@"
