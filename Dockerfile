FROM praekeltfoundation/python-base:alpine

# Install runtime dependencies for MC2 as well as Nginx and Redis
RUN apk --no-cache add libffi libpq \
    nginx redis

# Copy in bits of MC2 source we need
COPY mc2 /deploy/mc2
COPY manage.py \
    requirements.txt \
    requirements-dev.txt \
    setup.py \
    README.rst \
    VERSION \
    docker/docker-entrypoint.sh \
        /deploy/

ENV PROJECT_ROOT /deploy/
WORKDIR /deploy/

# Install MC2 as well as gunicorn and supervisor
RUN pip install gunicorn supervisor "Django<1.9,>=1.8" \
    && pip install -e .

# Set some basic config
ENV DJANGO_SETTINGS_MODULE mc2.settings
ENV MESOS_MARATHON_HOST http://servicehost:8080

# Copy in Nginx and Supervisor config
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/mc2.nginx.conf /etc/nginx/conf.d/
COPY docker/supervisord.conf /etc/supervisor/supervisord.conf
COPY docker/mc2.supervisor.conf /etc/supervisor/conf.d/

# Send Nginx access and error logs to stdout/stderr
RUN ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log

RUN mkdir -p /var/log/supervisor

EXPOSE 80
CMD ["/deploy/docker-entrypoint.sh"]
