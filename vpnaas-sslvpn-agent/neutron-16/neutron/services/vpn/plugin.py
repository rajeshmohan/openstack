
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
#    (c) Copyright 2013 Hewlett-Packard Development Company, L.P.
#    All Rights Reserved.
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
# @author: Swaminathan Vasudevan, Hewlett-Packard
from neutron.db.vpn import sslvpn_db
from neutron.db.vpn import vpn_credential_db
from neutron.db.vpn import vpn_db
from neutron.services.vpn.common import constants as vpn_consts
from neutron.services.vpn.service_drivers import ipsec as ipsec_driver
from neutron.services.vpn.service_drivers import sslvpn as sslvpn_driver


class VPNPlugin(object):
    """Implementation of the VPN Service Plugin.

    This class manages the workflow of VPNaaS request/response.
    Most DB related works are implemented in class
    vpn_db.VPNPluginDb.
    """
    supported_extension_aliases = ["vpnaas", "sslvpn", "vpncredential"]


class VPNIpsecDriverMixin(vpn_db.VPNPluginDb):
    """VpnPlugin which supports VPN IPSec Service Drivers."""
    #TODO(nati) handle ikepolicy and ipsecpolicy update usecase

    def _get_driver_for_ipsec_site_connection(self, context,
                                              ipsec_site_connection):
        vpnservice = vpn_consts.IPSEC
        return self._get_driver_for_vpnservice(vpnservice)

    def create_ipsec_site_connection(self, context, ipsec_site_connection):
        ipsec_site_connection = super(
            VPNIpsecDriverMixin, self).create_ipsec_site_connection(
                context, ipsec_site_connection)
        driver = self._get_driver_for_ipsec_site_connection(
            context, ipsec_site_connection)
        driver.create_ipsec_site_connection(context, ipsec_site_connection)
        return ipsec_site_connection

    def delete_ipsec_site_connection(self, context, ipsec_conn_id):
        ipsec_site_connection = self.get_ipsec_site_connection(
            context, ipsec_conn_id)
        super(VPNIpsecDriverMixin, self).delete_ipsec_site_connection(
            context, ipsec_conn_id)
        driver = self._get_driver_for_ipsec_site_connection(
            context, ipsec_site_connection)
        driver.delete_ipsec_site_connection(context, ipsec_site_connection)

    def update_ipsec_site_connection(
            self, context,
            ipsec_conn_id, ipsec_site_connection):
        old_ipsec_site_connection = self.get_ipsec_site_connection(
            context, ipsec_conn_id)
        ipsec_site_connection = super(
            VPNIpsecDriverMixin, self).update_ipsec_site_connection(
                context,
                ipsec_conn_id,
                ipsec_site_connection)
        driver = self._get_driver_for_ipsec_site_connection(
            context, ipsec_site_connection)
        driver.update_ipsec_site_connection(
            context, old_ipsec_site_connection, ipsec_site_connection)
        return ipsec_site_connection


class VPNSSLDriverMixin(sslvpn_db.SSLVPN_db_mixin,
                        vpn_credential_db.VPNCredential_db_mixin):
    """VPNSSLDriver Mixin."""

    def _get_driver_for_ssl_vpn_connection(self, context,
                                           ssl_vpn_connection):
        vpnservice = vpn_consts.SSL
        return self._get_driver_for_vpnservice(vpnservice)

    def create_ssl_vpn_connection(self, context, ssl_vpn_connection):
        ssl_vpn_connection = super(
            VPNSSLDriverMixin,
            self).create_ssl_vpn_connection(
                context, ssl_vpn_connection)
        driver = self._get_driver_for_ssl_vpn_connection(
            context, ssl_vpn_connection)
        driver.create_ssl_vpn_connection(context, ssl_vpn_connection)
        return ssl_vpn_connection

    def delete_ssl_vpn_connection(self, context, id):
        ssl_vpn_connection = self.get_ssl_vpn_connection(context, id)
        super(VPNSSLDriverMixin, self).delete_ssl_vpn_connection(context, id)
        driver = self._get_driver_for_ssl_vpn_connection(
            context, ssl_vpn_connection)
        driver.delete_ssl_vpn_connection(context, ssl_vpn_connection)

    def update_ssl_vpn_connection(self, context, id, ssl_vpn_connection_in):
        old_ssl_vpn_connection = self.get_ssl_vpn_connection(context, id)
        ssl_vpn_connection = super(
            VPNSSLDriverMixin, self).update_ssl_vpn_connection(
                context, id, ssl_vpn_connection_in)
        driver = self._get_driver_for_ssl_vpn_connection(
            context, ssl_vpn_connection)
        driver.update_ssl_vpn_connection(
            context, old_ssl_vpn_connection, ssl_vpn_connection)
        return ssl_vpn_connection


class VPNDriverPlugin(VPNPlugin,
                      VPNIpsecDriverMixin,
                      VPNSSLDriverMixin,
                      sslvpn_db.SSLVPN_PluginRpcDbMixin,
                      vpn_db.VPNPluginRpcDbMixin):
    """VpnPlugin which supports VPN Service Drivers."""
    #TODO(nati) handle ikepolicy and ipsecpolicy update usecase
    def __init__(self):
        self.drivers = {}
        self._add_driver_for_vpnservice(vpn_consts.IPSEC,
                                        ipsec_driver.IPsecVPNDriver(self))
        self._add_driver_for_vpnservice(vpn_consts.SSL,
                                        sslvpn_driver.SSLVPNDriver(self))
        super(VPNDriverPlugin, self).__init__()

    def _add_driver_for_vpnservice(self, vpnservice, driver):
        self.drivers[vpnservice] = driver

    def _get_driver_for_vpnservice(self, vpnservice):
        return self.drivers[vpnservice]

    def get_agent_hosting_vpn_services(self, context, host, vpntype):
        if vpntype == vpn_consts.SSL:
            return self._get_agent_hosting_sslvpn_services(context, host)
        else:
            return self._get_agent_hosting_vpn_services(context, host)

    def update_status_by_agent(
        self, context, service_status_info_list, vpntype):
        if vpntype == vpn_consts.SSL:
            return self._update_sslvpn_status_by_agent(
                context, service_status_info_list)
        else:
            return self._update_vpn_status_by_agent(
                context, service_status_info_list)

    def delete_vpnservice(self, context, vpnservice_id):
        vpnservice = self._get_vpnservice(context, vpnservice_id)
        super(VPNDriverPlugin, self).delete_vpnservice(
            context, vpnservice_id)
        for driver in self.drivers.values():
            driver.delete_vpnservice(context, vpnservice)
