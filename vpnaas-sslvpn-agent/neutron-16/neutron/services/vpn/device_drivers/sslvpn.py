# Copyright 2014
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
# @author: Rajesh Mohan, Rajesh_Mohan3@Dell.com, DELL Inc.
import abc
import copy
import netaddr
import os

from oslo.config import cfg
import six

from neutron.agent.linux import ip_lib
from neutron.agent.linux import utils
from neutron.common import rpc as q_rpc
from neutron import context
from neutron.openstack.common.gettextutils import _
from neutron.openstack.common import lockutils
from neutron.openstack.common import log as logging
from neutron.openstack.common import loopingcall
from neutron.openstack.common import rpc
from neutron.plugins.common import constants
from neutron.plugins.common import utils as plugin_utils
from neutron.services.vpn.common import topics
from neutron.services.vpn import device_drivers
from neutron.services.vpn.device_drivers import linux as linux_driver

LOG = logging.getLogger(__name__)
TEMPLATE_PATH = os.path.dirname(__file__)

sslvpn_opts = [
    cfg.StrOpt(
        'config_base_dir',
        default='$state_path/sslvpn',
        help=_('Location to store sslvpn server config files')),
    cfg.IntOpt('sslvpn_status_check_interval',
               default=60,
               help=_("Interval for checking sslvpn status"))
]
cfg.CONF.register_opts(sslvpn_opts, 'sslvpn')

openvpn_opts = [
    cfg.StrOpt(
        'sslvpn_config_template',
        default=os.path.join(
            TEMPLATE_PATH,
            'template/openvpn/sslvpn.conf.template'),
        help=_('Template file for sslvpn configuration'))
]

cfg.CONF.register_opts(openvpn_opts, 'openvpn')


class OpenVPNProcess(linux_driver.BaseLinuxProcess):
    """OpenVPN Process Manager

    This class manages start/restart/stop sslvpn process.
    This class creates/deletes config template
    """

    def __init__(self, conf, root_helper, process_id,
                 vpnservice, namespace):
        self.binary = "openvpn"
        self.config_dirs = [
            'var/run',
            'log',
            'etc',
            'etc/openvpn',
        ]

        self.dialect_map = {
        }

        config_dir = os.path.join(
            cfg.CONF.sslvpn.config_base_dir, process_id)
        self.pid_file = os.path.join(
            config_dir, 'var', 'run', 'openvpn.pid')
        self.tunnel_interface = 'tap0'
        super(OpenVPNProcess, self).__init__(
            conf, root_helper, process_id, vpnservice, namespace,
            config_dir)

    def get_connection_status(self, conn_id):
        if conn_id not in self._connection_status:
            self.connection_status[conn_id] = {
                'status': None
            }
        return self.connection_status[conn_id]

    def translate_dialect(self):
        if not self.vpnservice:
            return
        for ssl_vpn_connection in self.vpnservice['ssl_vpn_connections']:
            client_address_pool_cidr = ssl_vpn_connection[
                'client_address_pool_cidr']
            ssl_vpn_connection['pool'] = netaddr.IPNetwork(
                client_address_pool_cidr)

    def ensure_config_file(self, template, vpnservice):
        """Update config file,  based on current settings for service."""
        vpn_credential = vpnservice['ssl_vpn_connections'][0]['vpncredential']
        config_file_name = self._get_config_filename('ca.crt')
        utils.replace_file(config_file_name, vpn_credential['ca'],
                           permission=0o600)

        config_file_name = self._get_config_filename('server.crt')
        utils.replace_file(
            config_file_name, vpn_credential['server_certificate'],
            permission=0o600)

        config_file_name = self._get_config_filename('server.key')
        utils.replace_file(config_file_name, vpn_credential['server_key'],
                           permission=0o600)

        config_file_name = self._get_config_filename('dh1024.pem')
        utils.replace_file(config_file_name, vpn_credential['dh'],
                           permission=0o600)

        config_str = self._gen_config_content(template, vpnservice)
        config_file_name = self._get_config_filename('openvpn.conf')
        utils.replace_file(config_file_name, config_str)

    def _gen_config_content(self, template_file, vpnservice):
        template = linux_driver._get_template(template_file)
        openvpn_path = os.path.join(self.etc_dir, 'openvpn')
        return template.render(
            {'vpnservice': vpnservice,
             'ssl_vpn_connection': vpnservice['ssl_vpn_connections'][0],
             'openvpn_path': openvpn_path})

    def _get_config_filename(self, kind):
        config_dir = os.path.join(self.etc_dir, 'openvpn')
        return os.path.join(config_dir, kind)

    def _ensure_dir(self, dir_path):
        if not os.path.isdir(dir_path):
            os.makedirs(dir_path, 0o755)

    def ensure_config_dir(self, vpnservice):
        """Create config directory if it does not exist."""
        self._ensure_dir(self.config_dir)
        for subdir in self.config_dirs:
            dir_path = os.path.join(self.config_dir, subdir)
            self._ensure_dir(dir_path)

    @property
    def active(self):
        """Check if the process is active or not."""
        if not self.namespace:
            return False
        try:
            status = self.get_status()

            if status == constants.ACTIVE:
                return True
        except RuntimeError:
            return False
        return False

    def update(self):
        """Update Status based on vpnservice configuration."""
        super(OpenVPNProcess, self).update()

        self.vpnservice['status'] = self.status
        for ssl_vpn_conn in self.vpnservice['ssl_vpn_connections']:
            if plugin_utils.in_pending_status(ssl_vpn_conn['status']):
                conn_id = ssl_vpn_conn['id']
                conn_status = self.get_connection_status(conn_id)
                if not conn_status:
                    continue
                conn_status['updated_pending_status'] = True
                conn_status['status'] = self.vpnservice['status']
                ssl_vpn_conn['status'] = self.vpnservice['status']

    def _execute(self, cmd, check_exit_code=True):
        """Execute command on namespace."""
        ip_wrapper = ip_lib.IPWrapper(self.root_helper, self.namespace)
        return ip_wrapper.netns.execute(
            cmd,
            check_exit_code=check_exit_code)

    def ensure_configs(self):
        """Generate config files which are needed for OpenSwan.

        If there is no directory, this function will create
        dirs.
        """
        self.ensure_config_dir(self.vpnservice)
        self.ensure_config_file(
            self.conf.openvpn.sslvpn_config_template,
            self.vpnservice)

    def get_status(self):
        pid = self.pid
        if pid is None:
            return False
        cmdline = '/proc/%s/cmdline' % pid
        try:
            with open(cmdline, "r"):
                return constants.ACTIVE
        except IOError:
            return constants.DOWN

    def restart(self):
        """Restart the process."""
        self.stop()
        self.start()
        return

    def start(self):
        """Start the process.

        Note: if there is not namespace yet,
        just do nothing, and wait next event.
        """
        if not self.namespace:
            return
        config_file_name = self._get_config_filename('openvpn.conf')
        log_file = os.path.join(self.log_dir, 'openvpn.log')
        if not ip_lib.device_exists(self.tunnel_interface,
                                    root_helper=self.root_helper,
                                    namespace=self.namespace):
            #setup tun device
            self._execute([self.binary,
                           '--mktun',
                           '--dev', self.tunnel_interface,
                           ])

        device = ip_lib.IPDevice(self.tunnel_interface, self.root_helper,
                                 namespace=self.namespace)
        device.link.set_up()

        self._execute([self.binary,
                       '--tls-server',
                       '--daemon',
                       '--writepid', self.pid_file,
                       '--log-append', log_file,
                       '--config', config_file_name,
                       ])

    @property
    def pid(self):
        """Last known pid for the OpenVPN process spawned for this network."""
        try:
            with open(self.pid_file, 'r') as f:
                return int(f.read())
        except IOError:
            LOG.info('Unable to access %s', self.pid_file)
        return None

    def stop(self):
        pid = self.pid
        if pid:
            utils.execute(['kill', '-9', pid], root_helper=self.root_helper)
            os.remove(self.pid_file)
        if ip_lib.device_exists(self.tunnel_interface,
                                root_helper=self.root_helper,
                                namespace=self.namespace):
            device = ip_lib.IPDevice(
                self.tunnel_interface, self.root_helper,
                namespace=self.namespace)
            device.link.delete()


@six.add_metaclass(abc.ABCMeta)
class SSLVPNDriver(device_drivers.DeviceDriver):
    """VPN Device Driver for SSLVPN.

    This class is designed for use with L3-agent now.
    However this driver will be used with another agent in future.
    so the use of "Router" is kept minimul now.
    Insted of router_id,  we are using process_id in this code.
    """

    # history
    #   1.0 Initial version

    RPC_API_VERSION = '1.0'

    def __init__(self, agent, host):
        self.agent = agent
        self.conf = self.agent.conf
        self.root_helper = self.agent.root_helper
        self.host = host
        self.conn = rpc.create_connection(new=True)
        self.context = context.get_admin_context_without_session()
        self.topic = topics.SSL_VPN_AGENT_TOPIC
        node_topic = '%s.%s' % (self.topic, self.host)

        self.processes = {}
        self.process_status_cache = {}

        self.conn.create_consumer(
            node_topic,
            self.create_rpc_dispatcher(),
            fanout=False)
        self.conn.consume_in_thread()
        self.agent_rpc = linux_driver.VpnDriverApi(
            topics.SSL_VPN_DRIVER_TOPIC, '1.0')
        self.process_status_cache_check = loopingcall.FixedIntervalLoopingCall(
            self.report_status, self.context)
        self.process_status_cache_check.start(
            interval=self.conf.sslvpn.sslvpn_status_check_interval)

    def create_rpc_dispatcher(self):
        return q_rpc.PluginRpcDispatcher([self])

    def vpnservice_updated(self, context, **kwargs):
        """Vpnservice updated rpc handler

        VPN Service Driver will call this method
        when vpnservices updated.
        Then this method start sync with server.
        """

        self.sync(context, [])

    @abc.abstractmethod
    def create_process(self, process_id, vpnservice, namespace):
        pass

    def ensure_process(self, process_id, vpnservice=None):
        """Ensuring process.

        If the process doesn't exist, it will create process
        and store it in self.processs
        """
        process = self.processes.get(process_id)
        if not process or not process.namespace:
            namespace = self.agent.get_namespace(process_id)
            process = self.create_process(
                process_id,
                vpnservice,
                namespace)
            self.processes[process_id] = process
        return process

    def create_router(self, process_id):
        """Handling create router event.

        Agent calls this method, when the process namespace
        is ready.
        """
        if process_id in self.processes:
            # In case of vpnservice is created
            # before router's namespace
            process = self.processes[process_id]
            process.enable()

    def destroy_router(self, process_id):
        """Handling destroy_router event.

        Agent calls this method, when the process namespace
        is deleted.
        """
        if process_id in self.processes:
            process = self.processes[process_id]
            process.disable()
            del self.processes[process_id]

    def get_process_status_cache(self, process):
        if not self.process_status_cache.get(process.id):
            self.process_status_cache[process.id] = {
                'status': None,
                'id': process.vpnservice['id'],
                'updated_pending_status': False,
                'ssl_vpn_connections': {}}
        return self.process_status_cache[process.id]

    def is_status_updated(self, process, previous_status):
        if process.updated_pending_status:
            return True
        if process.status != previous_status['status']:
            return True
        if (process.connection_status !=
            previous_status['ssl_vpn_connections']):
            return True

    def unset_updated_pending_status(self, process):
        process.updated_pending_status = False
        for connection_status in process.connection_status.values():
            connection_status['updated_pending_status'] = False

    def copy_process_status(self, process):
        return {
            'id': process.vpnservice['id'],
            'status': process.status,
            'updated_pending_status': process.updated_pending_status,
            'ssl_vpn_connections': copy.deepcopy(process.connection_status)
        }

    def report_status(self, context):
        status_changed_vpn_services = []
        for process in self.processes.values():
            previous_status = self.get_process_status_cache(process)
            if self.is_status_updated(process, previous_status):
                new_status = self.copy_process_status(process)
                self.process_status_cache[process.id] = new_status
                status_changed_vpn_services.append(new_status)
                # We need unset updated_pending status after it
                # is reported to the server side
                self.unset_updated_pending_status(process)

        if status_changed_vpn_services:
            self.agent_rpc.update_status(
                context,
                status_changed_vpn_services)

    @lockutils.synchronized('vpn-agent', 'neutron-')
    def sync(self, context, routers):
        """Sync status with server side.

        :param context: context object for RPC call
        :param routers: Router objects which is created in this sync event

        There could be many failure cases should be
        considered including the followings.
        1) Agent class restarted
        2) Failure on process creation
        3) VpnService is deleted during agent down
        4) RPC failure

        In order to handle, these failure cases,
        This driver takes simple sync strategies.
        """
        vpnservices = self.agent_rpc.get_vpn_services_on_host(
            context, self.host)
        router_ids = [vpnservice['router_id'] for vpnservice in vpnservices]
        # Ensure the sslvpn process is enabled
        for vpnservice in vpnservices:
            process = self.ensure_process(vpnservice['router_id'],
                                          vpnservice=vpnservice)
            process.update()

        # Delete any SSLVPN processes that are
        # associated with routers, but are not running the VPN service.
        for router in routers:
            #We are using router id as process_id
            process_id = router['id']
            if process_id not in router_ids:
                process = self.ensure_process(process_id)
                self.destroy_router(process_id)

        # Delete any SSLVPN processes running
        # VPN that do not have an associated router.
        process_ids = [process_id
                       for process_id in self.processes
                       if process_id not in router_ids]
        for process_id in process_ids:
            self.destroy_router(process_id)
        self.report_status(context)


class OpenVPNDriver(SSLVPNDriver):
    def create_process(self, process_id, vpnservice, namespace):
        return OpenVPNProcess(
            self.conf,
            self.root_helper,
            process_id,
            vpnservice,
            namespace)
