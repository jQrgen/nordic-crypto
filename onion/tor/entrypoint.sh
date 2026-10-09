#!/bin/sh
# Starts Tor as debian-tor after the key volume is writable. Prints nothing about tips.
set -eu
mkdir -p /var/lib/tor/tip
chown -R debian-tor:debian-tor /var/lib/tor
chmod 700 /var/lib/tor /var/lib/tor/tip
exec su -s /bin/sh debian-tor -c 'exec tor -f /etc/tor/torrc'
