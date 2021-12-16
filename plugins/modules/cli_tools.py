#!/usr/bin/python
# Copyright: (c) 2022, Nick Curry <code@nickcurry.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
import os
import tarfile
import shutil
from collections.abc import MutableMapping
import urllib3
from ansible.module_utils.basic import AnsibleModule


DOCUMENTATION = r'''
---
module: cli_tools
short_description: Module to download and manage OpenShift / OKD CLI tools
description:
- This module is used to download common CLI tools used when administering OpenShift / OKD clusters.
author:
- Nick Curry (@nccurry)
notes:
requirements:
- python >= 3.5
options:
    symlink:
      description:
      - Whether to symlink the unversioned cli to the versioned one
      - For example symlink oc -> oc-4.9.10
      type: bool
      default: false
    executable_directory:
      description:
      - Directory where executables are installed
      type: str
      default: %{HOME}/bin
    executable:
      description:
      - Which executable to install
      type: str
      default: okd
      choices:
      - openshift-install
      - okd-install
      - oc
    release:
      description:
      - Version of the executable tools to install
      type: str
    state:
      description:
      - The state of the tools
      - If set to C(present) and tools do not exist, then they are installed.
      - If set to C(present) and tools exist, then this module will result in no change.
      - If set to C(absent) and tools exist, then they are removed.
      - If set to C(absent) and items do not exist, then this module will result in no change.
      type: str
      default: 'present'
      choices: [ 'present', 'absent' ]
'''

EXAMPLES = r'''
# Install CLI tools for OKD / OpenShift
- name: Install openshift-install for OpenShift 4.9.10 and create symlink /usr/local/bin/oc -> /usr/local/bin/oc-4.9.10
  nccurry.openshift.cli_tools:
    executable_directory: /usr/local/bin
    executable: openshift-install
    release: 4.9.10
    symlink: true
    
- name: Install all cli tools for OKD / OpenShift
  nccurry.openshift.cli_tools:
    executable: "{{ item.name }}"
    release: "{{ item.version }}"
    symlink: true
  loop:
  - name: openshift-install
    version: 4.9.10
  - name: okd-install
    version: 4.9.0-0.okd-2021-11-28-035710
  - name: oc
    version: 4.9.10
    
- name: Install okd-install
  nccurry.openshift.cli_tools:
    executable: okd-install
    release: 4.9.0-0.okd-2021-11-28-035710
    
- name: Uninstall okd-install
  nccurry.openshift.cli_tools:
    executable: okd-install
    release: 4.9.0-0.okd-2021-11-28-035710
    state: absent
    
- name: Uninstall all cli tools for OKD / OpenShift
  nccurry.openshift.cli_tools:
    executable: "{{ item.name }}"
    release: "{{ item.version }}"
    symlink: true
    state: absent
  loop:
  - name: openshift-install
    version: 4.9.10
  - name: okd-install
    version: 4.9.0-0.okd-2021-11-28-035710
  - name: oc
    version: 4.9.10
'''

RETURN = r'''
cli_tools:
  description: List of CLI executables information
  returned: on success
  type: dict
  sample: {
      "okd-install": {
          "path": "/home/user/bin/okd-install-4.9.0-0.okd-2021-12-12-025847",
          "symlink": "/home/user/bin/okd-install"
      }
  }
'''


class CollectionAnsibleModule:
    """Parent class representing the functionality of an Ansible collection module"""
    def __init__(self, module):
        self._module: AnsibleModule = module
        self._result: dict = dict(changed=False)

    # https://stackoverflow.com/a/24088493/2394163
    def _merge_dicts(self, first: dict, second: dict) -> dict:
        """Merge two dict objects recursively

        Update two dicts of dicts recursively,
        if either mapping has leaves that are non-dicts,
        the second's leaf overwrites the first's.

        Parameters
        ----------
        first : dict
            First dict
        second : dict
            Second dict
        """
        for k, v in first.items():
            if k in second:
                if all(isinstance(e, MutableMapping) for e in (v, second[k])):
                    second[k] = self._merge_dicts(v, second[k])
        d3 = first.copy()
        d3.update(second)
        return d3

    def _update_result(self, new_data: dict):
        """Merge new data into the result dict

        Parameters
        ----------
        new_data : dict
            Additional data to merge into the result struct
        """
        self._result = self._merge_dicts(self._result, new_data)

    def _changed(self):
        """Indicate that Ansible should report a change, will exit if Ansible is in check_mode"""
        self._result['changed'] = True
        if self._module.check_mode:
            self._exit()

    def _fail(self, error: str):
        """Indicate that Ansible should fail, will exit immediately

        Parameters
        ----------
        error : str
            Error message for Ansible to display
        """
        self._module.fail_json(msg=error, **self._result)

    def _exit(self):
        """Indicate that Ansible should exit"""
        self._module.exit_json(**self._result)


class CliToolsModule(CollectionAnsibleModule):
    """Class representing the functionality of this Ansible collection module"""
    def __init__(self, module):
        # Initialize superclass methods
        super().__init__(module)

        self._update_result({'cli_tools': {}})

        # Module parameters
        self.symlink = module.params.get('symlink')
        self.executable_directory = module.params.get('executable_directory')
        self.executable = module.params.get('executable')
        self.release = module.params.get('release')
        self.state = module.params.get('state')

    def tar_gz_download_url(self):
        """Return the https download url of an executables tar.gz archive"""
        if self.executable == "okd-install":
            return f"https://github.com/openshift/okd/releases/download/{self.release}/openshift-install-linux-{self.release}.tar.gz"

        if self.executable == "openshift-install":
            return f"https://mirror.openshift.com/pub/openshift-v4/clients/ocp/{self.release}/openshift-install-linux.tar.gz"

        if self.executable == "oc":
            # OKD oc versions contain the text okd - i.e. 4.9.0-0.okd-2021-12-12-025847
            if "okd" in self.release:
                return f"https://github.com/openshift/okd/releases/download/{self.release}/openshift-client-linux-{self.release}.tar.gz"

            return f"https://mirror.openshift.com/pub/openshift-v4/clients/ocp/{self.release}/openshift-client-linux.tar.gz"

    @staticmethod
    def file_exists(path: str) -> bool:
        """Determine whether a file exists

        Parameters
        ----------
        path : str
            The file path

        Returns
        ----------
        exists : bool
            True if the file exists
        """
        return os.path.isfile(path) or os.path.islink(path) or os.path.isdir(path)

    def download_file(self, path: str, url: str):
        """Download a file over http

        Parameters
        ----------
        path : str
            The first parameter.
        url : str
            The second parameter.
        """
        if not self.file_exists(path):
            try:
                self._changed()
                pool_manager = urllib3.PoolManager()

                response = pool_manager.request('GET', url, preload_content=False)
                if response.status != 200:
                    self._fail(f"There was a problem downloading file at {url}: {response.status} - {response.reason}")

                with open(path, 'wb') as file:
                    shutil.copyfileobj(response, file)

            except Exception as error:
                self._fail(repr(error))

    def extract_tar_gz(self, tar_path: str, extract_path: str):
        """Unarchive a tar.gz file

        Parameters
        ----------
        tar_path : str
            Path to tar.gz file
        extract_path : str
            Directory to unarchive contents into
        """
        if not self.file_exists(extract_path):
            try:
                self._changed()
                with tarfile.open(tar_path) as file:
                    file.extractall(extract_path)

            except Exception as error:
                self._fail(repr(error))

    def delete_file(self, path: str):
        """Delete a file or directory

        Parameters
        ----------
        path : str
            The path to the file or directory
        """
        if self.file_exists(path):
            try:
                self._changed()
                if os.path.islink(path):
                    os.unlink(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)

            except Exception as error:
                self._fail(repr(error))

    def copy_executable(self, src: str, dest: str):
        """Copy a file and make it executable

        Parameters
        ----------
        src : str
            The source path to the file
        dest : str
            The target path to copy it to
        """
        if not self.file_exists(dest):
            try:
                self._changed()
                shutil.move(src, dest)
                os.chmod(dest, 0o775)

            except Exception as error:
                self._fail(repr(error))

    def create_symlink(self, link: str, target: str):
        """Create or move a symlink

        Parameters
        ----------
        link : str
            The symlink to create
        target : str
            The target of the symlink
        """
        existing_target = ""

        try:
            existing_target = os.readlink(link)

        # If there isn't a symlink already, no problem
        except FileNotFoundError:
            pass

        except Exception as error:
            self._fail(repr(error))

        try:
            if existing_target != target:
                self._changed()
                if self.file_exists(link):
                    os.remove(link)
                os.symlink(target, link)

        except Exception as error:
            self._fail(repr(error))

    def install_executable(self):
        """Download executable tar.gz, unarchive it, copy it to the executable directory, and symlink it if desired"""
        # We rename openshift-install to okd-install for OKD
        tar_name = "openshift-install" if self.executable == "okd-install" else self.executable

        # Download file and extract tar.gz
        if not self.file_exists(path=f"{self.executable_directory}/{self.executable}-{self.release}"):
            self.download_file(path=f"/tmp/{self.executable}.tar.gz", url=self.tar_gz_download_url())
            self.extract_tar_gz(tar_path=f"/tmp/{self.executable}.tar.gz", extract_path=f"/tmp/{self.executable}")
            self.copy_executable(src=f"/tmp/{self.executable}/{tar_name}", dest=f"{self.executable_directory}/{self.executable}-{self.release}")
        self._update_result({'cli_tools': {self.executable: {'path': f"{self.executable_directory}/{self.executable}-{self.release}"}}})

        # Create symlink
        if self.symlink:
            self.create_symlink(link=f"{self.executable_directory}/{self.executable}", target=f"{self.executable_directory}/{self.executable}-{self.release}")
            self._update_result({'cli_tools': {self.executable: {'symlink': f"{self.executable_directory}/{self.executable}"}}})

        # Cleanup
        self.delete_file(path=f"/tmp/{self.executable}")
        self.delete_file(path=f"/tmp/{self.executable}")

    def uninstall_executable(self):
        """Uninstall executable and any intermediary files"""
        self.delete_file(path=f"/tmp/{self.executable}.tar.gz")
        self.delete_file(path=f"/tmp/{self.executable}")

        self.delete_file(f"{self.executable_directory}/{self.executable}-{self.release}")
        if self.symlink:
            self.delete_file(f"{self.executable_directory}/{self.executable}")

    def process_state(self):
        """Entrypoint into Ansible module"""
        if self.state == 'present':
            self.install_executable()
        elif self.state == 'absent':
            self.uninstall_executable()
        self._exit()


def main():
    module_args = dict(
        symlink=dict(type='bool', default=False),
        executable_directory=dict(type='str', default=f"{os.environ['HOME']}/bin"),
        executable=dict(type='str', required=True, choices=['okd-install', 'openshift-install', 'oc']),
        release=dict(type='str', required=True),
        state=dict(type='str', choices=['present', 'absent'], default='present')
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    cli_tools_module = CliToolsModule(module)
    cli_tools_module.process_state()


if __name__ == '__main__':
    main()
