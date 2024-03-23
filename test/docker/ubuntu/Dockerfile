FROM ubuntu:22.04

RUN apt update
RUN apt -y upgrade
RUN apt install -y sudo

# timezone
RUN ln -sf /usr/share/zoneinfo/Asia/Tokyo /etc/localtime
RUN apt install -y git tzdata

# ruby
RUN apt install -y ruby gem ruby-dev bundler
RUN apt install -y g++ make 

# tool
RUN apt install -y net-tools
RUN apt install -y wget gnupg2
RUN apt install -y less
RUN apt install -y x11-xserver-utils
RUN apt install -y vim

# google chrome
RUN echo "deb http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.list
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
RUN apt update
RUN apt install -y google-chrome-stable

# PythonUmlClass
RUN apt install -y plantuml
RUN apt install -y pip
RUN pip install astor

CMD ["/bin/bash"]

ENV USERNAME=ubuntu
RUN adduser ${USERNAME}
RUN gpasswd -a ${USERNAME} sudo
RUN echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
USER ${USERNAME}

