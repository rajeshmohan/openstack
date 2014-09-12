# Copyright 2014, Nachi Ueno, NTT I3, Inc.
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
from neutron.common import rpc as n_rpc
from neutron import manager
from neutron.openstack.common import log as logging
from neutron.openstack.common.rpc import proxy
from neutron.plugins.common import constants


LOG = logging.getLogger(__name__)

BASE_VPN_VERSION = '1.0'


class VpnDriverCallBack(object):
    """Callback for VpnDriver rpc."""

    # history
    #   1.0 Initial version

    RPC_API_VERSION = BASE_VPN_VERSION

    def __init__(self, driver):
        self.driver = driver

    def create_rpc_dispatcher(self):
        return n_rpc.PluginRpcDispatcher([self])

    def get_vpn_services_on_host(self, context, host=None):
        """Retuns the vpnservices on the host."""
        plugin = self.driver.service_plugin
        vpnservices = plugin.get_agent_hosting_vpn_services(
            context, host, self.driver.service_type)
        return [self.driver._make_vpnservice_dict(vpnservice)
                for vpnservice in vpnservices]

    def update_status(self, context, status):
        """Update status of vpnservices."""
        plugin = self.driver.service_plugin
        plugin.update_status_by_agent(
            context, status, self.driver.service_type)


class VpnAgentApi(proxy.RpcProxy):
    """Agent RPC API for VPNAgent."""

    RPC_API_VERSION = BASE_VPN_VERSION

    def _agent_notification(self, context, method, router_id,
                            agent_topic, version=None):
        """Notify update for the agent.

        This method will find where is the router, and
        dispatch notification for the agent.
        """
        adminContext = context.is_admin and context or context.elevated()
        plugin = manager.NeutronManager.get_service_plugins().get(
            constants.L3_ROUTER_NAT)
        if not version:
            version = self.RPC_API_VERSION
        l3_agents = plugin.get_l3_agents_hosting_routers(
            adminContext, [router_id],
            admin_state_up=True,
            active=True)
        for l3_agent in l3_agents:
            LOG.debug(_('Notify agent at %(topic)s.%(host)s the message '
                        '%(method)s'),
                      {'topic': agent_topic,
                       'host': l3_agent.host,
                       'method': method})
            self.cast(
                context, self.make_msg(method),
                version=version,
                topic='%s.%s' % (agent_topic, l3_agent.host))

    def vpnservice_updated(self, context, router_id, topic):
        """Send update event of vpnservices."""
        method = 'vpnservice_updated'
        self._agent_notification(context, method, router_id, topic)
