# Copyright 2016 Cloudbase Solutions Srl
# All Rights Reserved.

from oslo_log import log as logging

from coriolis.osmorphing.osmount import base
from coriolis import utils

LOG = logging.getLogger(__name__)


class RedHatOSMountTools(base.BaseLinuxOSMountTools):
    def check_os(self):
        # make sure the package redhat-lsb-core is installed
        os_info = utils.get_linux_os_info(self._ssh)
        if os_info and os_info[0] in [
                'RedHatEnterpriseServer', 'CentOS', 'OracleServer',
                'rhel', 'centos', 'ol']:
            return True

    def setup(self):
        super(RedHatOSMountTools, self).setup()
        self._exec_cmd("sudo -E yum install -y lvm2")
        self._exec_cmd("sudo modprobe dm-mod")

    def _allow_ssh_env_vars(self):
        self._exec_cmd('sudo sed -i -e "\$aAcceptEnv *" /etc/ssh/sshd_config')
        self._exec_cmd("sudo service sshd reload")
        return True
