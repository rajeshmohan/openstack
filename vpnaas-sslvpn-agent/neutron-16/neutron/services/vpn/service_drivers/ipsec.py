# vim: tabstop=10 shiftwidth=4 softtabstop=4
#
# Copyright 2013, Nachi Ueno, NTT I3, Inc.
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
import netaddr

from neutron.openstack.common import log as logging
from neutron.openstack.common import rpc
from neutron.services.vpn.common import constants as vpn_consts
from neutron.services.vpn.common import topics
from neutron.services.vpn import service_drivers
from neutron.services.vpn.service_drivers import vpn


LOG = logging.getLogger(__name__)

BASE_IPSEC_VERSION = '1.0'


class IPsecVPNDriver(service_drivers.VpnDriver):
    """VPN Service Driver class for IPsec."""

    def __init__(self, service_plugin):
        self.callbacks = vpn.VpnDriverCallBack(self)
        self.service_plugin = service_plugin
        self.conn = rpc.create_connection(new=True)
        self.conn.create_consumer(
            topics.IPSEC_DRIVER_TOPIC,
            self.callbacks.create_rpc_dispatcher(),
            fanout=False)
        self.conn.consume_in_thread()
        self.agent_rpc = vpn.VpnAgentApi(
            topics.IPSEC_AGENT_TOPIC, BASE_IPSEC_VERSION)

    @property
    def service_type(self):
        return vpn_consts.IPSEC

    def create_ipsec_site_connection(self, context, ipsec_site_connection):
        vpnservice = self.service_plugin._get_vpnservice(
            context, ipsec_site_connection['vpnservice_id'])
        self.agent_rpc.vpnservice_updated(context, vpnservice['router_id'],
                                          topics.IPSEC_AGENT_TOPIC)

    def update_ipsec_site_connection(
        self, context, old_ipsec_site_connection, ipsec_site_connection):
        vpnservice = self.service_plugin._get_vpnservice(
            context, ipsec_site_connection['vpnservice_id'])
        self.agent_rpc.vpnservice_updated(context, vpnservice['router_id'],
                                          topics.IPSEC_AGENT_TOPIC)

    def delete_ipsec_site_connection(self, context, ipsec_site_connection):
        vpnservice = self.service_plugin._get_vpnservice(
            context, ipsec_site_connection['vpnservice_id'])
        self.agent_rpc.vpnservice_updated(context, vpnservice['router_id'],
                                          topics.IPSEC_AGENT_TOPIC)

    def create_ikepolicy(self, context, ikepolicy):
        pass

    def delete_ikepolicy(self, context, ikepolicy):
        pass

    def update_ikepolicy(self, context, old_ikepolicy, ikepolicy):
        pass

    def create_ipsecpolicy(self, context, ipsecpolicy):
        pass

    def delete_ipsecpolicy(self, context, ipsecpolicy):
        pass

    def update_ipsecpolicy(self, context, old_ipsec_policy, ipsecpolicy):
        pass

    def create_vpnservice(self, context, vpnservice):
        pass

    def update_vpnservice(self, context, old_vpnservice, vpnservice):
        self.agent_rpc.vpnservice_updated(context, vpnservice['router_id'],
                                          topics.IPSEC_AGENT_TOPIC)

    def delete_vpnservice(self, context, vpnservice):
        self.agent_rpc.vpnservice_updated(context, vpnservice['router_id'],
                                          topics.IPSEC_AGENT_TOPIC)

    def _make_vpnservice_dict(self, vpnservice):
        """Convert vpnservice information for vpn agent.

        also converting parameter name for vpn agent driver
        """
        vpnservice_dict = dict(vpnservice)
        vpnservice_dict['ipsec_site_connections'] = []
        vpnservice_dict['subnet'] = dict(
            vpnservice.subnet)
        vpnservice_dict['external_ip'] = vpnservice.router.gw_port[
            'fixed_ips'][0]['ip_address']
        for ipsec_site_connection in vpnservice.ipsec_site_connections:
            ipsec_site_connection_dict = dict(ipsec_site_connection)
            try:
                netaddr.IPAddress(ipsec_site_connection['peer_id'])
            except netaddr.core.AddrFormatError:
                ipsec_site_connection['peer_id'] = (
                    '@' + ipsec_site_connection['peer_id'])
            ipsec_site_connection_dict['ikepolicy'] = dict(
                ipsec_site_connection.ikepolicy)
            ipsec_site_connection_dict['ipsecpolicy'] = dict(
                ipsec_site_connection.ipsecpolicy)
            vpnservice_dict['ipsec_site_connections'].append(
                ipsec_site_connection_dict)
            peer_cidrs = [
                peer_cidr.cidr
                for peer_cidr in ipsec_site_connection.peer_cidrs]
            ipsec_site_connection_dict['peer_cidrs'] = peer_cidrs
        return vpnservice_dict