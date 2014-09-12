# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 OpenStack Foundation.
# All Rights Reserved.
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#         http://www.apache.org/licenses/LICENSE-2.0
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
from sqlalchemy.orm import exc
import uuid

from neutron.common import constants as n_constants
from neutron.common import exceptions as q_exc
from neutron.db import db_base_plugin_v2 as base_db
from neutron.db import l3_agentschedulers_db as l3_agent_db
from neutron.db.vpn import vpn_db
from neutron.extensions.sslvpn import SSLVPNPluginBase
from neutron.extensions import vpnaas
from neutron import manager
from neutron.openstack.common import log as logging
from neutron.plugins.common import constants
from neutron.plugins.common import utils

LOG = logging.getLogger(__name__)


class SSLVPNConnectionNotFound(q_exc.NotFound):
    message = _(
        "SSLVPNConnection %(conn_id)s could not be found")


class SSLVPN_db_mixin(SSLVPNPluginBase,
                      base_db.CommonDbMixin):
    def _get_resource(self, context, model, id):
        return self._get_by_id(context, model, id)

    def update_status(self, context, resource_name, resource_id, status):
        resource_name_to_method = {
            "ssl_vpn_connection": self._update_ssl_vpn_connection,
            "credential": self._update_credential,
        }
        update_method = resource_name_to_method[resource_name]
        content_dict = {'status': status}
        return update_method(context, resource_id, content_dict)

    def create_ssl_vpn_connection(self, context, ssl_vpn_connection):
        ssl_vpn_connection_in = ssl_vpn_connection['ssl_vpn_connection']
        tenant_id = self._get_tenant_id_for_create(
            context, ssl_vpn_connection_in)
        with context.session.begin(subtransactions=True):
            ssl_vpn_connection_db = vpn_db.SSLVPNConnection(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                name=ssl_vpn_connection_in['name'],
                credential_id=ssl_vpn_connection_in['credential_id'],
                admin_state_up=ssl_vpn_connection_in['admin_state_up'],
                vpnservice_id=ssl_vpn_connection_in['vpnservice_id'],
                client_address_pool_cidr=ssl_vpn_connection_in[
                    'client_address_pool_cidr'],
                status=constants.PENDING_CREATE
            )
            context.session.add(ssl_vpn_connection_db)

        ssl_vpn_connection_db = self._get_resource(
            context,
            vpn_db.SSLVPNConnection,
            ssl_vpn_connection_db['id'])
        return self._make_ssl_vpn_connection_dict(ssl_vpn_connection_db)

    def get_ssl_vpn_connections(self, context, filters=None, fields=None):
        return self._get_collection(context, vpn_db.SSLVPNConnection,
                                    self._make_ssl_vpn_connection_dict,
                                    filters=filters, fields=fields)

    def _make_ssl_vpn_connection_dict(self,
                                      ssl_vpn_connection,
                                      fields=None):
        res = {
            'id': ssl_vpn_connection['id'],
            'tenant_id': ssl_vpn_connection['tenant_id'],
            'name': ssl_vpn_connection['name'],
            'credential_id': ssl_vpn_connection['credential_id'],
            'admin_state_up': ssl_vpn_connection['admin_state_up'],
            'vpnservice_id': ssl_vpn_connection['vpnservice_id'],
            'client_address_pool_cidr': ssl_vpn_connection[
                'client_address_pool_cidr'],
            'status': ssl_vpn_connection['status'],
        }
        return self._fields(res, fields)

    def get_ssl_vpn_connection(self, context, id, fields=None):
        try:
            ssl_vpn_connection = self._get_resource(
                context, vpn_db.SSLVPNConnection, id)
        except exc.NoResultFound:
            raise vpn_db.SSLVPNConnectionNotFound(conn_id=id)
        return self._make_ssl_vpn_connection_dict(ssl_vpn_connection, fields)

    def _update_ssl_vpn_connection(self, context, id, ssl_vpn_connection):
        with context.session.begin(subtransactions=True):
            ssl_vpn_connection_db = self._get_resource(
                context,
                vpn_db.SSLVPNConnection,
                id)
            if ssl_vpn_connection:
                ssl_vpn_connection_db.update(ssl_vpn_connection)
        return ssl_vpn_connection_db

    def update_ssl_vpn_connection(self, context, id, ssl_vpn_connection_in):
        ssl_vpn_connection = ssl_vpn_connection_in['ssl_vpn_connection']
        res = self._update_ssl_vpn_connection(context, id, ssl_vpn_connection)
        return self._make_ssl_vpn_connection_dict(res)

    def delete_ssl_vpn_connection(self, context, id):
        with context.session.begin(subtransactions=True):
            ssl_vpn_connection_db = self._get_resource(
                context,
                vpn_db.SSLVPNConnection,
                id)
            context.session.delete(ssl_vpn_connection_db)


class SSLVPN_PluginRpcDbMixin():
    def _get_agent_hosting_sslvpn_services(self, context, host):

        plugin = manager.NeutronManager.get_plugin()
        agent = plugin._get_agent_by_type_and_host(
            context, n_constants.AGENT_TYPE_L3, host)
        if not agent.admin_state_up:
            return []
        query = context.session.query(vpn_db.VPNService)
        query = query.join(vpn_db.SSLVPNConnection)
        query = query.join(l3_agent_db.RouterL3AgentBinding,
                           l3_agent_db.RouterL3AgentBinding.router_id ==
                           vpn_db.VPNService.router_id)
        query = query.filter(
            l3_agent_db.RouterL3AgentBinding.l3_agent_id == agent.id)
        return query

    def _update_sslvpn_status_by_agent(
        self, context, service_status_info_list):
        """Updating vpnservice and vpnconnection status.

        :param context: context variable
        :param service_status_info_list: list of status
        The structure is
        [{id: vpnservice_id,
          status: ACTIVE|DOWN|ERROR,
          updated_pending_status: True|False
          ssl_vpn_connections: {
              ssl_vpn_connection_id: {
                  status: ACTIVE|DOWN|ERROR,
                  updated_pending_status: True|False
              }
          }]
        The agent will set updated_pending_status as True,
        when agent update any pending status.
        """
        with context.session.begin(subtransactions=True):
            for vpnservice in service_status_info_list:
                try:
                    vpnservice_db = self._get_vpnservice(
                        context, vpnservice['id'])
                except vpnaas.VPNServiceNotFound:
                    LOG.warn(_('vpnservice %s in db is already deleted'),
                             vpnservice['id'])
                    continue

                if (not utils.in_pending_status(vpnservice_db.status)
                    or vpnservice['updated_pending_status']):
                    vpnservice_db.status = vpnservice['status']
                for conn_id, conn in vpnservice[
                    'ssl_vpn_connections'].items():
                    try:
                        conn_db = self._get_resource(
                            context, vpn_db.SSLVPNConnection, conn_id)

                    except SSLVPNConnectionNotFound:
                        continue
                    if (not utils.in_pending_status(conn_db.status)
                        or conn['updated_pending_status']):
                        conn_db.status = conn['status']
