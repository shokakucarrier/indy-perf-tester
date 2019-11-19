FROM quay.io/openshift/origin-jenkins-agent-base:v4.0

#FROM registry.access.redhat.com/rhel7:latest
#FROM centos:7

MAINTAINER NOS Team

LABEL com.redhat.component="jenkins-agent-maven-pme-perftest-rhel7-container" \
      name="openshift3/jenkins-agent-maven-pme-perftest-rhel7" \
      version="3.11" \
      architecture="x86_64" \
      io.k8s.display-name="Jenkins Agent Indy Perf Tester" \
      io.k8s.description="The jenkins agent indy-perf-tester image has the maven + PME + indy-perf-tester tools on top of the jenkins slave base image." \
      io.openshift.tags="openshift,jenkins,agent,maven,PME,indy-perf-tester"

ENV TZ=UTC \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
	JAVA_HOME=/usr/lib/jvm/java-1.8.0-openjdk

USER root

ADD pki/Eng_Ops_CA.crt /etc/pki/ca-trust/source/anchors/Eng_Ops_CA.crt
ADD pki/Red_Hat_IS_CA.crt /etc/pki/ca-trust/source/anchors/Red_Hat_IS_CA.crt
ADD pki/RH-IT-Root-CA.crt /etc/pki/ca-trust/source/anchors/RH-IT-Root-CA.crt
RUN update-ca-trust extract

ARG disables="--disablerepo=rhel-server-extras --disablerepo=rhel-server --disablerepo=rhel-fast-datapath --disablerepo=rhel-server-optional --disablerepo=rhel-server-ose --disablerepo=rhel-server-rhscl"

RUN yum $disables -y update && \
	yum $disables -y install git wget which tar gzip bzip2 unzip zip lsof \
				   strace perf tcpdump iproute \
				   java-1.8.0-openjdk-devel java-1.8.0-openjdk-headless java-1.8.0-openjdk-headless \
				   python3 python3-pip python-virtualenv && \
	yum $disables clean all && \
	git config --system http.sslCAInfo /etc/pki/ca-trust/source/anchors/RH-IT-Root-CA.crt && \
	sed -i 's/jdk.tls.disabledAlgorithms=SSLv3/jdk.tls.disabledAlgorithms=EC,ECDHE,ECDH,SSLv3/g' $JAVA_HOME/jre/lib/security/java.security && \
	chmod u+s /usr/sbin/chpasswd /usr/sbin/xtables-multi /usr/sbin/tcpdump

#Install maven
# set installed Maven version you can easily change it later
ENV MAVEN_VERSION 3.3.9
ENV PME_VERSION 3.8.1

# NCL-4067: remove useless download progress with batch mode (-B)
RUN curl -SL http://archive.apache.org/dist/maven/maven-3/$MAVEN_VERSION/binaries/apache-maven-$MAVEN_VERSION-bin.tar.gz | tar xzf - -C /usr/share

RUN mkdir -p /usr/share/pme && chmod ugo+x /usr/share/pme
RUN curl -SLo  /usr/share/pme/pme.jar https://repo.maven.apache.org/maven2/org/commonjava/maven/ext/pom-manipulation-cli/$PME_VERSION/pom-manipulation-cli-$PME_VERSION.jar

RUN mv /usr/share/apache-maven-$MAVEN_VERSION /usr/share/maven

RUN sed -i 's|${CLASSWORLDS_LAUNCHER} "$@"|${CLASSWORLDS_LAUNCHER} -B "$@"|g' /usr/share/maven/bin/mvn

RUN ln -s /usr/share/maven/bin/mvn /usr/bin/mvn

RUN echo "export M2_HOME=/usr/share/maven" >> /etc/profile

RUN chgrp -R 0 /usr/share/maven && \
    chmod -R g=u /usr/share/maven


# ---------------------------------------------------------------
# END BASE IMAGE SETUP
# ---------------------------------------------------------------


RUN mkdir -p /usr/share/indy-perf-tester/indyperf

ADD indyperf /usr/share/indy-perf-tester/indyperf
ADD setup.py /usr/share/indy-perf-tester
ADD scripts/* /usr/local/bin/

RUN chmod +x /usr/local/bin/*

RUN virtualenv --python=$(which python3) /usr/share/indy-perf-tester/venv && \
	/usr/share/indy-perf-tester/venv/bin/pip install --upgrade pip && \
	/usr/share/indy-perf-tester/venv/bin/pip install -e /usr/share/indy-perf-tester

USER 1001
