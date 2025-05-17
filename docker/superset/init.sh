#!/bin/sh
set -e

# Initialize the database
superset db upgrade

# Create an admin user
superset fab create-admin \
    --username "$SUPERSET_ADMIN_USERNAME" \
    --firstname "$SUPERSET_ADMIN_FIRSTNAME" \
    --lastname "$SUPERSET_ADMIN_LASTNAME" \
    --email "$SUPERSET_ADMIN_EMAIL" \
    --password "$SUPERSET_ADMIN_PASSWORD"

# Create default roles and permissions
superset init

if [ "$SUPERSET_LOAD_EXAMPLES" = "yes" ]; then
    # Load some data to play with
    superset load_examples --force
fi
