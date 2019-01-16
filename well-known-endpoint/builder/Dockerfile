FROM amazonlinux:2

# Base dependencies
RUN yum update -y
RUN yum install @development wget -y
RUN yum install python python-dev python-pip -y
ADD requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt

RUN echo -n "PS1=\"[deploy-shell][\u@\h \W]\$ \"" >> /root/.bashrc

# Setup a home for deployment
RUN mkdir -p /project

# Force this as the entrypoint
WORKDIR /project
