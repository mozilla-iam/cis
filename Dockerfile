FROM amazonlinux:2
LABEL maintainer="akrug@mozilla.com"

# Base image
RUN \
  yum makecache fast && \
  yum install -y \
                  glibc-devel \
                  gcc \
                  libstdc++ \
                  libffi-devel \
                  zlib-devel \
                  make \
                  openssl \
                  openssl-dev \
                  which \
                  net-tools \
                  wget \
                  procps-ng-3.3.10-17.amzn2.2.2.x86_64

RUN echo -n "PS1=\"[cis-dev-preview][\u@\h \W]\$ \"" >> /root/.bashrc
# Adding Python3
RUN yum install python3 python3-devel python3-pip python-pip -y

# Adding NodeJS 8.x LTS'
RUN wget https://rpm.nodesource.com/setup_8.x \
    && bash setup_8.x \
    && yum -y install nodejs

# Adding kinesalite and dynalite packages'
WORKDIR /opt/cis/envs/venv/
RUN npm install kinesalite \
    && npm install dynalite \
    && npm install leveldown \
    && mkdir /opt/dynamodb_data \
    && mkdir /opt/kinesis_data

# Install nginx
RUN amazon-linux-extras install nginx1.12 -y

# Setting up supervisord
RUN pip install supervisor

# Configure
COPY docker/config/supervisor.conf /opt/cis/conf/
COPY docker/config/mozilla-cis.ini /etc/mozilla-cis.ini
COPY docker/config/nginx.conf /etc/nginx/nginx.conf

# Setting up CIS
RUN mkdir -p /var/log/cis \
    && mkdir -p /opt/cis/conf \
    && mkdir -p /opt/cis \
    && mkdir -p /opt/cis/envs
ADD . /opt/cis

# Install CIS modules
RUN python3 -m venv /opt/cis/venv
ENV VIRTUAL_ENV="/opt/cis/venv"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install iam_profile_faker
RUN bash -c '\
  for D in $(find /opt/cis/python-modules -mindepth 1 -maxdepth 1 -type d) ; \
  do pip3 install $D ; done; \
  pip install iam_profile_faker'

CMD ['/usr/bin/supervisord', '-c', '/opt/cis/docker/config/supervisor.conf']
