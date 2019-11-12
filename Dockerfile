FROM registry.access.redhat.com/rhel7:latest
#FROM centos:7
MAINTAINER NOS Team

LABEL io.openshift.sti.scripts-url="image:///usr/local/sti" \
    io.openshift.s2i.scripts-url="image:///usr/local/sti" \
    Component="pnc-sti-base" \
    Name="pnc/pnc-rhel-7-base" \
    Version="7" \
    Release="1"

USER root

# NCL-2855: All services should run with UTC timezone
ENV TZ UTC

# NCL-4310: Set the lang to US UTF-8
ENV LANG en_US.UTF-8

ADD pki/Eng_Ops_CA.crt /etc/pki/ca-trust/source/anchors/Eng_Ops_CA.crt
ADD pki/Red_Hat_IS_CA.crt /etc/pki/ca-trust/source/anchors/Red_Hat_IS_CA.crt
ADD pki/RH-IT-Root-CA.crt /etc/pki/ca-trust/source/anchors/RH-IT-Root-CA.crt
RUN update-ca-trust extract

RUN yum -y update && \
	yum -y install git wget which tar gzip bzip2 unzip zip lsof strace perf tcpdump iproute && \
	yum -y install http://download.eng.bos.redhat.com/brewroot/packages/java-1.8.0-openjdk/1.8.0.121/0.b13.el7_3/x86_64/java-1.8.0-openjdk-devel-1.8.0.121-0.b13.el7_3.x86_64.rpm \
	  http://download.eng.bos.redhat.com/brewroot/packages/java-1.8.0-openjdk/1.8.0.121/0.b13.el7_3/x86_64/java-1.8.0-openjdk-1.8.0.121-0.b13.el7_3.x86_64.rpm \
	  http://download.eng.bos.redhat.com/brewroot/packages/java-1.8.0-openjdk/1.8.0.121/0.b13.el7_3/x86_64/java-1.8.0-openjdk-headless-1.8.0.121-0.b13.el7_3.x86_64.rpm

# NCL-2916: update-ca-trust has no effect on Openshift pods
RUN git config --system http.sslCAInfo /etc/pki/ca-trust/source/anchors/RH-IT-Root-CA.crt

# set JAVA_HOME: needed for some builds
ENV JAVA_HOME /usr/lib/jvm/java-1.8.0-openjdk

# openjdk bug with SSL connection https://bugzilla.redhat.com/show_bug.cgi?id=1167153
RUN sed -i 's/jdk.tls.disabledAlgorithms=SSLv3/jdk.tls.disabledAlgorithms=EC,ECDHE,ECDH,SSLv3/g' $JAVA_HOME/jre/lib/security/java.security

RUN chmod u+s /usr/sbin/chpasswd /usr/sbin/xtables-multi /usr/sbin/tcpdump

#Install maven
# set installed Maven version you can easily change it later
ENV MAVEN_VERSION 3.3.9
ENV PME_VERSION 3.8.1

# NCL-4067: remove useless download progress with batch mode (-B)
RUN curl -sSL http://archive.apache.org/dist/maven/maven-3/$MAVEN_VERSION/binaries/apache-maven-$MAVEN_VERSION-bin.tar.gz | tar xzf - -C /usr/share \
	&& curl -sSLo  /usr/share/pom-manipulation-cli.jar https://repo.maven.apache.org/maven2/org/commonjava/maven/ext/pom-manipulation-cli/$PME_VERSION/pom-manipulation-cli-$PME_VERSION.jar \
	&& mv /usr/share/apache-maven-$MAVEN_VERSION /usr/share/maven \
	&& sed -i 's|${CLASSWORLDS_LAUNCHER} "$@"|${CLASSWORLDS_LAUNCHER} -B "$@"|g' /usr/share/maven/bin/mvn \
	&& ln -s /usr/share/maven/bin/mvn /usr/bin/mvn

RUN echo "export M2_HOME=/usr/share/maven" >> /etc/profile

RUN chgrp -R 0 /usr/share/maven && \
    chmod -R g=u /usr/share/maven

RUN yum -y install python3 python3-pip python-virtualenv && \
	yum clean all


# ---------------------------------------------------------------
# END BASE IMAGE SETUP
# ---------------------------------------------------------------


RUN mkdir /usr/share/indy-perf-tester

ADD app.py /usr/share/indy-perf-tester
ADD requirements.txt /usr/share/indy-perf-tester

RUN virtualenv --python=$(which python3) /usr/share/indy-perf-tester/venv && \
	/usr/share/indy-perf-tester/venv/bin/pip install --upgrade -r /usr/share/indy-perf-tester/requirements.txt

USER 1001

ENTRYPOINT ["/usr/share/indy-perf-tester/venv/bin/python", "/usr/share/indy-perf-tester/app.py"]
