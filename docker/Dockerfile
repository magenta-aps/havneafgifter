# SPDX-FileCopyrightText: 2024 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0

FROM python:3.12
ENV SUPERCRONIC_URL=https://github.com/aptible/supercronic/releases/download/v0.2.27/supercronic-linux-amd64 \
    SUPERCRONIC=supercronic-linux-amd64 \
    SUPERCRONIC_SHA1SUM=7dadd4ac827e7bd60b386414dfefc898ae5b6c63\
    PYTHONUNBUFFERED=1

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN mkdir /app && \
    mkdir -p /var/cache/havneafgift && \
    mkdir /static && \
    mkdir -p /storage/pdf && \
    #gid/uid from salt
    groupadd -g 75170 -r havneafgifter && \
    groupadd -g 75100 -r certificate_exporter && \
    useradd -u 75170 --no-log-init -r -g havneafgifter -G certificate_exporter havneafgifter && \
    chown -R havneafgifter:havneafgifter /app && \
    chown -R havneafgifter:havneafgifter /static && \
    chmod a+w /static && \
    chown -R havneafgifter:havneafgifter /var/cache/havneafgift && \
    chmod a+w /var/cache/havneafgift && \
    chown -R havneafgifter:havneafgifter /storage/pdf && \
    chmod a+w /storage/pdf

# Font cache for pdf generation
RUN mkdir -p /home/havneafgifter/.cache/fontconfig && \
    chown -R havneafgifter /home/havneafgifter/.cache/fontconfig

# hadolint ignore=DL3008
RUN sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list' && \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/postgresql.gpg && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        gettext python3-distutils graphviz libxmlsec1-dev xmlsec1 libssl-dev libsasl2-dev postgresql-client-common postgresql-client-16 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# supercronic
RUN curl -fsSLO "$SUPERCRONIC_URL" && \
    echo "${SUPERCRONIC_SHA1SUM}  ${SUPERCRONIC}" | sha1sum -c - && \
    chmod +x "$SUPERCRONIC" && \
    mv "$SUPERCRONIC" "/usr/local/bin/${SUPERCRONIC}" && \
    ln -s "/usr/local/bin/${SUPERCRONIC}" /usr/local/bin/supercronic

ARG COMMIT_TAG
ENV COMMIT_TAG=${COMMIT_TAG:-HEAD}

COPY requirements.txt /app/requirements.txt
COPY mypy.ini /app/mypy.ini

RUN pip install --no-cache-dir -r /app/requirements.txt &&  \
    rm /app/requirements.txt

ARG COMMIT_TAG
ENV COMMIT_TAG=${COMMIT_TAG:-HEAD}

COPY --chown=havneafgifter:havneafgifter ./havneafgifter /app
RUN chown -R havneafgifter:havneafgifter /app
COPY ./docker/entrypoint.sh /entrypoint.sh
EXPOSE 8000
USER havneafgifter
ENTRYPOINT ["/entrypoint.sh"]
WORKDIR /app
RUN django-admin compilemessages --locale=kl --locale=da --locale=en

CMD ["gunicorn","-b","0.0.0.0:8000","project.wsgi:application","-w","4","--timeout","120","--error-logfile","-","--capture-output"]
