# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/xenial64"

  # Mount the first workflow path found;
  # Unfortunately VirtualBox cannot mount symlinks or junctions, so there are different paths for different machines
  workflow_paths = ["E:/Workflow", "C:/Workflow"].select { |path| File.directory?(path) }
  if !workflow_paths.empty?
    config.vm.synced_folder workflow_paths[0], "/workflow"
  end

  config.vm.provider 'virtualbox' do |vb|
    # Work around "Rejecting I/O to offline device" issue
    vb.customize ["storagectl", :id, "--name", "SCSI Controller", "--hostiocache", "on"]
  end

  # Install python
  config.vm.provision :shell, name: "Install Python", inline: "apt-get update && apt-get install -y python3 python3-pip"

  # Install script dependencies from Python
  config.vm.provision :shell, name: "Install script dependencies from Python", inline: "python3 -m pip install --upgrade -r /vagrant/requirements.txt"

  # Make it easier to test things in Vagrant
  config.vm.provision :shell, inline: <<-SHELL
    apt-get install -y tree recode
    echo 'cd /vagrant' >> ~ubuntu/.profile
    ln -nsf /vagrant/.bash_history ~ubuntu/
  SHELL
end
