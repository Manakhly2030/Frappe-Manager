#!/usr/bin/bash

# wait for all the programs to load first
echo "Waiting for mailhog,adminer,rq to start"
wait-for-it -t 120 mailhog:8025
wait-for-it -t 120 adminer:8080
wait-for-it -t 120 rq-dashboard:9181

/config/jinja2 -D SITENAME="$SITENAME" /config/template.conf > /etc/nginx/conf.d/default.conf

nginx -g 'daemon off;'
