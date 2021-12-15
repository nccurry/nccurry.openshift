#!/usr/bin/python
# Copyright: (c) 2022, Nick Curry <code@nickcurry.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
import os
import tarfile
import shutil
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
    install_type:
      description:
      - Install OpenShift or OKD tools
      type: str
      default: okd
      choices:
      - ocp
      - okd
      - both
    okd_release:
      description:
      - Version of OKD tools to install
      type: str
    ocp_release:
      description:
      - Version of OpenShift tools to install
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
# Install CLI tools for OpenShift
- name: Install CLI tools
  nccurry.openshift.install_cli_tools:
    symlink: true
    executable_directory: /usr/local/bin
    install_type: ocp
    ocp_release: 4.9.10
    
# Install CLI tools for OKD
- name: Install CLI tools
  nccurry.openshift.install_cli_tools:
    install_type: okd
    okd_release: 4.9.0-0.okd-2021-11-28-035710
    
# Install CLI tools for OpenShift and OKD
- name: Install CLI tools
  nccurry.openshift.install_cli_tools:
    symlink: true
    install_type: both
    ocp_release: 4.9.10
    okd_release: 4.9.0-0.okd-2021-11-28-035710
    
# Remove CLI tools
- name: Uninstall CLI tools
  nccurry.openshift.install_cli_tools:
    install_type: both
    ocp_release: 4.9.10
    okd_release: 4.9.0-0.okd-2021-11-28-035710
    state: absent
'''

RETURN = r'''
'''


class CollectionAnsibleModule:
    def __init__(self, module):
        self._module: AnsibleModule = module
        self._result: dict = dict(changed=False)

    def _changed(self):
        self._result['changed'] = True
        if self._module.check_mode:
            self._exit()

    def _fail(self, error: str):
        self._module.fail_json(msg=error, **self._result)

    def _exit(self):
        self._module.exit_json(**self._result)


class CliToolsModule(CollectionAnsibleModule):
    def __init__(self, module):
        # Initialize superclass methods
        super().__init__(module)

        # Module parameters
        self.symlink = module.params.get('symlink')
        self.executable_directory = module.params.get('executable_directory')
        self.install_type = module.params.get('install_type')
        self.okd_release = module.params.get('okd_release')
        self.ocp_release = module.params.get('ocp_release')
        self.state = module.params.get('state')

    @staticmethod
    def okd_install_tar_gz_url(okd_release: str) -> str:
        return f"https://github.com/openshift/okd/releases/download/{okd_release}/openshift-install-linux-{okd_release}.tar.gz"

    @staticmethod
    def okd_oc_tar_gz_url(okd_release: str) -> str:
        return f"https://github.com/openshift/okd/releases/download/{okd_release}/openshift-client-linux-{okd_release}.tar.gz"

    @staticmethod
    def openshift_install_tar_gz_url(ocp_release: str) -> str:
        return f"https://mirror.openshift.com/pub/openshift-v4/clients/ocp/{ocp_release}/openshift-install-linux.tar.gz"

    @staticmethod
    def openshift_oc_install_tar_gz_url(ocp_release: str) -> str:
        return f"https://mirror.openshift.com/pub/openshift-v4/clients/ocp/{ocp_release}/openshift-client-linux.tar.gz"

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
        if self.file_exists(path):
            return

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

    def process_state(self):
        """Entrypoint into Ansible module"""
        if self.state == 'present':
            if self.install_type == 'okd':
                # okd-install
                if not self.file_exists(path=f"{self.executable_directory}/okd-install-{self.okd_release}"):
                    self.download_file(path="/tmp/okd_install.tar.gz", url=self.okd_install_tar_gz_url(self.okd_release))
                    self.extract_tar_gz(tar_path="/tmp/okd_install.tar.gz", extract_path="/tmp/okd_install")
                    self.copy_executable(src="/tmp/okd_install/openshift-install", dest=f"{self.executable_directory}/okd-install-{self.okd_release}")

                if self.symlink:
                    self.create_symlink(link=f"{self.executable_directory}/okd-install", target=f"{self.executable_directory}/okd-install-{self.okd_release}")

                self.delete_file(path="/tmp/okd_install.tar.gz")
                self.delete_file(path="/tmp/okd_install")

                # oc
                if not self.file_exists(path=f"{self.executable_directory}/oc-{self.okd_release}"):
                    self.download_file(path="/tmp/oc.tar.gz", url=self.okd_oc_tar_gz_url(self.okd_release))
                    self.extract_tar_gz(tar_path="/tmp/oc.tar.gz", extract_path="/tmp/oc")
                    self.copy_executable(src="/tmp/oc/oc", dest=f"{self.executable_directory}/oc-{self.okd_release}")

                if self.symlink:
                    self.create_symlink(link=f"{self.executable_directory}/oc", target=f"{self.executable_directory}/oc-{self.okd_release}")

                self.delete_file(path="/tmp/oc.tar.gz")
                self.delete_file(path="/tmp/oc")

            elif self.install_type == 'ocp':
                # openshift-install
                if not self.file_exists(f"{self.executable_directory}/openshift-install-{self.ocp_release}"):
                    self.download_file(path="/tmp/openshift_install.tar.gz", url=self.openshift_install_tar_gz_url(self.ocp_release))
                    self.extract_tar_gz(tar_path="/tmp/openshift_install.tar.gz", extract_path="/tmp/openshift_install")
                    self.copy_executable(src="/tmp/openshift_install/openshift-install", dest=f"{self.executable_directory}/openshift-install-{self.ocp_release}")

                if self.symlink:
                    self.create_symlink(link=f"{self.executable_directory}/openshift-install", target=f"{self.executable_directory}/openshift-install-{self.ocp_release}")

                self.delete_file(path="/tmp/openshift_install.tar.gz")
                self.delete_file(path="/tmp/openshift_install")

                # oc
                if not self.file_exists(f"{self.executable_directory}/oc-{self.ocp_release}"):
                    self.download_file(path="/tmp/oc.tar.gz", url=self.openshift_oc_install_tar_gz_url(self.ocp_release))
                    self.extract_tar_gz(tar_path="/tmp/oc.tar.gz", extract_path="/tmp/oc")
                    self.copy_executable(src="/tmp/oc/oc", dest=f"{self.executable_directory}/oc-{self.ocp_release}")

                if self.symlink:
                    self.create_symlink(link=f"{self.executable_directory}/oc", target=f"{self.executable_directory}/oc-{self.ocp_release}")

                self.delete_file(path="/tmp/oc.tar.gz")
                self.delete_file(path="/tmp/oc")

            else:
                # okd-install
                if not self.file_exists(path=f"{self.executable_directory}/okd-install-{self.okd_release}"):
                    self.download_file(path="/tmp/okd_install.tar.gz", url=self.okd_install_tar_gz_url(self.okd_release))
                    self.extract_tar_gz(tar_path="/tmp/okd_install.tar.gz", extract_path="/tmp/okd_install")
                    self.copy_executable(src="/tmp/okd_install/openshift-install", dest=f"{self.executable_directory}/okd-install-{self.okd_release}")

                if self.symlink:
                    self.create_symlink(link=f"{self.executable_directory}/okd-install", target=f"{self.executable_directory}/okd-install-{self.okd_release}")

                self.delete_file(path="/tmp/okd_install.tar.gz")
                self.delete_file(path="/tmp/okd_install")

                # openshift-install
                if not self.file_exists(f"{self.executable_directory}/openshift-install-{self.ocp_release}"):
                    self.download_file(path="/tmp/openshift_install.tar.gz", url=self.openshift_install_tar_gz_url(self.ocp_release))
                    self.extract_tar_gz(tar_path="/tmp/openshift_install.tar.gz", extract_path="/tmp/openshift_install")
                    self.copy_executable(src="/tmp/openshift_install/openshift-install", dest=f"{self.executable_directory}/openshift-install-{self.ocp_release}")

                if self.symlink:
                    self.create_symlink(link=f"{self.executable_directory}/openshift-install", target=f"{self.executable_directory}/openshift-install-{self.ocp_release}")

                self.delete_file(path="/tmp/openshift_install.tar.gz")
                self.delete_file(path="/tmp/openshift_install")

                # oc
                if not self.file_exists(f"{self.executable_directory}/oc-{self.ocp_release}"):
                    self.download_file(path="/tmp/oc.tar.gz", url=self.openshift_oc_install_tar_gz_url(self.ocp_release))
                    self.extract_tar_gz(tar_path="/tmp/oc.tar.gz", extract_path="/tmp/oc")
                    self.copy_executable(src="/tmp/oc/oc", dest=f"{self.executable_directory}/oc-{self.ocp_release}")

                if self.symlink:
                    self.create_symlink(link=f"{self.executable_directory}/oc", target=f"{self.executable_directory}/oc-{self.ocp_release}")

                self.delete_file(path="/tmp/oc.tar.gz")
                self.delete_file(path="/tmp/oc")

        elif self.state == 'absent':
            if self.install_type in ["okd", "both"]:
                self.delete_file(path="/tmp/okd_install.tar.gz")
                self.delete_file(path="/tmp/okd_install")

                self.delete_file(f"{self.executable_directory}/okd-install-{self.okd_release}")
                self.delete_file(f"{self.executable_directory}/oc-{self.okd_release}")
                if self.symlink:
                    self.delete_file(f"{self.executable_directory}/okd-install")
                    self.delete_file(f"{self.executable_directory}/oc")

            if self.install_type in ["ocp", "both"]:
                self.delete_file(path="/tmp/openshift_install.tar.gz")
                self.delete_file(path="/tmp/openshift_install")

                self.delete_file(f"{self.executable_directory}/openshift-install-{self.ocp_release}")
                self.delete_file(f"{self.executable_directory}/oc-{self.ocp_release}")
                if self.symlink:
                    self.delete_file(f"{self.executable_directory}/openshift-install")
                    self.delete_file(f"{self.executable_directory}/oc")

            self.delete_file(path="/tmp/oc.tar.gz")
            self.delete_file(path="/tmp/oc")

        self._exit()


def main():
    module_args = dict(
        symlink=dict(type='bool', default=False),
        executable_directory=dict(type='str', default=f"{os.environ['HOME']}/bin"),
        install_type=dict(type='str', default='okd', choices=['okd', 'ocp', 'both']),
        okd_release=dict(type='str'),
        ocp_release=dict(type='str'),
        state=dict(type='str', choices=['present', 'absent'], default='present')
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        required_if=[
            ('state', 'present', ('okd_release', 'ocp_release'), True),
            ('state', 'absent', ('okd_release', 'ocp_release'), True),
            ('install_type', 'both', ('okd_release', 'ocp_release'), False)
        ]
    )

    cli_tools_module = CliToolsModule(module)
    cli_tools_module.process_state()


if __name__ == '__main__':
    main()
