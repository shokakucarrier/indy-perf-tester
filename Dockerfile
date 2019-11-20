FROM quay.io/openshift/origin-jenkins-agent-base:v4.0

MAINTAINER NOS Team

ENV TZ=UTC \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
	JAVA_HOME=/usr/lib/jvm/java-1.8.0-openjdk

#USER root

ARG MAVEN_VERSION=3.3.9
ARG	PME_VERSION=3.8.1

ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8

# Install Maven
RUN INSTALL_PKGS="java-1.8.0-openjdk-devel.x86_64 python3 python3-pip python-virtualenv" && \
    curl https://raw.githubusercontent.com/cloudrouter/centos-repo/master/CentOS-Base.repo -o /etc/yum.repos.d/CentOS-Base.repo && \
    curl http://mirror.centos.org/centos-7/7/os/x86_64/RPM-GPG-KEY-CentOS-7 -o /etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-7 && \
    DISABLES="--disablerepo=rhel-server-extras --disablerepo=rhel-server --disablerepo=rhel-fast-datapath --disablerepo=rhel-server-optional --disablerepo=rhel-server-ose --disablerepo=rhel-server-rhscl" && \
    yum $DISABLES -y update && \
    yum $DISABLES install -y $INSTALL_PKGS && \
    rpm -V java-1.8.0-openjdk-devel.x86_64 && \
    yum clean all -y && \
    mkdir -p $HOME/.m2 

RUN chown -R 1001:0 $HOME && \
    chmod -R g+rw $HOME

ADD pki/* /etc/pki/ca-trust/source/anchors/
RUN update-ca-trust extract

RUN	sed -i 's/jdk.tls.disabledAlgorithms=SSLv3/jdk.tls.disabledAlgorithms=EC,ECDHE,ECDH,SSLv3/g' $JAVA_HOME/jre/lib/security/java.security

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

#ENTRYPOINT ["/bin/bash"]