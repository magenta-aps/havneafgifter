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
CREATE_GROUPS=${CREATE_GROUPS:=false}
CREATE_DUMMY_ADMIN=${CREATE_DUMMY_ADMIN:=false}
CREATE_DUMMY_STAFF=${CREATE_DUMMY_STAFF:=false}
SKIP_IDP_METADATA=${SKIP_IDP_METADATA:=false}

python manage.py wait_for_db

if [ "${MAKE_MIGRATIONS,,}" = true ]; then
  echo 'generating migrations'
  python manage.py makemigrations --no-input
fi
if [ "${MIGRATE,,}" = true ]; then
  echo 'running migrations'
  python manage.py migrate
fi


if [ "${LOAD_FIXTURES}" = true ]; then
  python manage.py load_fixtures
fi

if [ "${CREATE_GROUPS}" = true ]; then
  echo 'creating groups'
  ./manage.py create_groups
fi

if [ "${CREATE_DUMMY_ADMIN}" = true ]; then
  echo 'creating superuser'
  DJANGO_SUPERUSER_PASSWORD=admin DJANGO_SUPERUSER_USERNAME=admin DJANGO_SUPERUSER_EMAIL=admin@admin.admin ./manage.py createsuperuser --noinput
fi

if [ "${CREATE_DUMMY_STAFF}" = true ]; then
  echo 'creating tax user'
  ./manage.py createuser tax tax -s -g TaxAuthority
  echo 'creating shipping user'
  ./manage.py createuser shipping shipping -s -g Shipping
  echo 'creating portauthority user'
  ./manage.py createuser portauthority portauthority -s -g PortAuthority
fi

python manage.py createcachetable
if [ "${SKIP_IDP_METADATA,,}" = false ]; then
  python manage.py update_mitid_idp_metadata
fi

echo 'collecting static files'
python manage.py collectstatic --no-input --clear

if [ "${TEST,,}" = true ]; then
  echo 'running tests'
  coverage run manage.py test
  coverage combine
  coverage report --show-missing
fi
if [ "${MAKEMESSAGES,,}" = true ]; then
  echo 'making messages'
  python manage.py makemessages --locale=kl --no-obsolete --add-location file
  python manage.py makemessages --locale=da --no-obsolete --add-location file
  python manage.py makemessages --locale=en --no-obsolete --add-location file
fi
if [ "${COMPILEMESSAGES,,}" = true ]; then
  echo 'compiling messages'
  python manage.py compilemessages --locale=kl
  python manage.py compilemessages --locale=da
  python manage.py compilemessages --locale=en
fi

exec "$@"
