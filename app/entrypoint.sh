#!/bin/sh
# Steward container entrypoint.
#
# Runs DB migrations + collectstatic before exec'ing the CMD so production
# images "just work" out of the docker-compose up. Either step can be skipped
# by setting the matching env var to 0 -- useful for sidecars like qcluster
# that share the same image but do not own schema or static collection.

set -eu

if [ "${STEWARD_RUN_MIGRATIONS:-1}" != "0" ]; then
    echo "[entrypoint] migrate"
    python manage.py migrate --noinput
fi

if [ "${STEWARD_COLLECTSTATIC:-1}" != "0" ]; then
    echo "[entrypoint] collectstatic"
    python manage.py collectstatic --noinput
fi

exec "$@"
