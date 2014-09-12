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
from neutron.openstack.common import log as logging
from neutron.openstack.common import rpc
from neutron.services.vpn.common import constants as vpn_consts
from neutron.services.vpn.common import topics
from neutron.services.vpn import service_drivers
from neutron.services.vpn.service_drivers import vpn


LOG = logging.getLogger(__name__)

BASE_SSLVPN_VERSION = '1.0'


class SSLVPNDriver(service_drivers.VpnDriver):
    """VPN Service Driver class for SSL VPN."""

    def __init__(self, service_plugin):
        self.callbacks = vpn.VpnDriverCallBack(self)
        self.service_plugin = service_plugin
        self.conn = rpc.create_connection(new=True)
        self.conn.create_consumer(
            topics.SSL_VPN_DRIVER_TOPIC,
            self.callbacks.create_rpc_dispatcher(),
            fanout=False)
        self.conn.consume_in_thread()
        self.agent_rpc = vpn.VpnAgentApi(
            topics.SSL_VPN_AGENT_TOPIC, BASE_SSLVPN_VERSION)

    @property
    def service_type(self):
        return vpn_consts.SSL

    def create_ssl_vpn_connection(self, context, ssl_vpn_connection):
        vpnservice = self.service_plugin._get_vpnservice(
            context, ssl_vpn_connection['vpnservice_id'])
        self.agent_rpc.vpnservice_updated(context, vpnservice['router_id'],
                                          topics.SSL_VPN_AGENT_TOPIC)

    def update_ssl_vpn_connection(self, context, old_ssl_vpn_connection,
                                  ssl_vpn_connection):
        vpnservice = self.service_plugin._get_vpnservice(
            context, ssl_vpn_connection['vpnservice_id'])
        self.agent_rpc.vpnservice_updated(context, vpnservice['router_id'],
                                          topics.SSL_VPN_AGENT_TOPIC)

    def delete_ssl_vpn_connection(self, context, ssl_vpn_connection):
        vpnservice = self.service_plugin._get_vpnservice(
            context, ssl_vpn_connection['vpnservice_id'])
        self.agent_rpc.vpnservice_updated(context, vpnservice['router_id'],
                                          topics.SSL_VPN_AGENT_TOPIC)

    def create_vpnservice(self, context, vpnservice):
        pass

    def update_vpnservice(self, context, old_vpnservice, vpnservice):
        self.agent_rpc.vpnservice_updated(context, vpnservice['router_id'],
                                          topics.SSL_VPN_AGENT_TOPIC)

    def delete_vpnservice(self, context, vpnservice):
        self.agent_rpc.vpnservice_updated(context, vpnservice['router_id'],
                                          topics.SSL_VPN_AGENT_TOPIC)

    def _make_vpnservice_dict(self, vpnservice):
        """Convert vpnservice information for vpn agent.

        also converting parameter name for vpn agent driver
        """
        vpnservice_dict = dict(vpnservice)
        vpnservice_dict['ssl_vpn_connections'] = []
        for ssl_vpn_connection in vpnservice.ssl_vpn_connections:
            ssl_vpn_connection_dict = dict(ssl_vpn_connection)
            ssl_vpn_connection_dict['vpncredential'] = dict(
                ssl_vpn_connection.vpn_credential)
            vpnservice_dict['ssl_vpn_connections'].append(
                ssl_vpn_connection_dict)
        return vpnservice_dict
