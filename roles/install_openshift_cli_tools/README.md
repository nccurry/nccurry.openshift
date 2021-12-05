Install OpenShift CLI Tools
=========

This role can be used to install common OpenShift / OKD CLI tools to an Ansible command host. 

Requirements
------------

This is tested on a host running the following
* Ansible 5.0.1
* Fedora 35

Role Variables
--------------

| Variable | Required | Default | Choices | Comments |
|-------------------------|----------|---------|---------------------------|------------------------------------------|
| create_symlinks | no | true | true, false| Whether to create a symlink from the individual unversioned CLI name to the versioned one - i.e. oc -> oc-4.9.10 |
| binary_directory | no | ${HOME}/bin | Any linux directory path | Where to install the CLI tools |
| install_type | no | ocp | okd, ocp | Whether to install OpenShift or OKD CLI tools |
| okd_release | no | 4.9.0-0.okd-2021-11-28-035710 | [Any OKD release version](https://amd64.origin.releases.ci.openshift.org/) | Version of CLI tools to install |
| ocp_release | no | 4.9.10 | [Any OpenShift release version](https://amd64.ocp.releases.ci.openshift.org/) | Version of CLI tools to install |
| teardown | no | false | true, false | If teardown is set to true, remove everything |

Dependencies
------------

Before using this role you must install the collection

```shell
ansible-galaxy install collection nccurry.openshift
```

Example Playbook
----------------

```yaml
#!/usr/bin/env ansible-playbook
---
- name: Download OpenShift CLI tools
  hosts: localhost
  gather_facts: false
  tasks:
  - vars:
      install_type: okd
      okd_release: 4.8.0-0.okd-2021-11-14-052418
    import_role:
      name: nccurry.openshift.install_openshift_cli_tools
```

License
-------

MIT

Author Information
------------------

Nick Curry

code@nickcurry.com

https://nickcurry.com
