#!/bin/sh
set -eu

APP_BASE_PATH=$(printf '%s' "$APP_BASE_PATH" | sed 's:/*$::')
if ! printf '%s' "$APP_BASE_PATH" | grep -Eq '^(/[A-Za-z0-9_-]+)+$'; then
    echo 'Invalid APP_BASE_PATH: use a non-root path such as /tradebridge.' >&2
    exit 1
fi
if [ "$APP_BASE_PATH" != "$(cat /etc/nginx/app-base-path)" ]; then
    echo 'APP_BASE_PATH differs from the frontend build. Rebuild the image.' >&2
    exit 1
fi
# Child exports do not reach the official entrypoint's later envsubst step.
sed -i "s|\${APP_BASE_PATH}|$APP_BASE_PATH|g" /etc/nginx/templates/default.conf.template
