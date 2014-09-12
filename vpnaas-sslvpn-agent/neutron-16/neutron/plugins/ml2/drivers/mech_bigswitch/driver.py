# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2014 Big Switch Networks, Inc.
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
# @author: Sumit Naiksatam, sumitnaiksatam@gmail.com, Big Switch Networks, Inc.

from oslo.config import cfg

from neutron import context as ctx
from neutron.extensions import portbindings
from neutron.openstack.common import log
from neutron.plugins.bigswitch.db import porttracker_db
from neutron.plugins.bigswitch.plugin import NeutronRestProxyV2Base
from neutron.plugins.bigswitch.plugin import ServerPool
from neutron.plugins.ml2 import driver_api as api


LOG = log.getLogger(__name__)


class BigSwitchMechanismDriver(NeutronRestProxyV2Base,
                               api.MechanismDriver):

    """Mechanism Driver for Big Switch Networks Controller.

    This driver relays the network create, update, delete
    operations to the Big Switch Controller.
    """

    def initialize(self, server_timeout=None):
        LOG.debug(_('Initializing driver'))

        # backend doesn't support bulk operations yet
        self.native_bulk_support = False

        # init network ctrl connections
        self.servers = ServerPool(server_timeout)
        self.segmentation_types = ', '.join(cfg.CONF.ml2.type_drivers)
        LOG.debug(_("Initialization done"))

    def create_network_postcommit(self, context):
        # create network on the network controller
        self._send_create_network(context.current)

    def update_network_postcommit(self, context):
        # update network on the network controller
        self._send_update_network(context.current)

    def delete_network_postcommit(self, context):
        # delete network on the network controller
        self._send_delete_network(context.current)

    def create_port_postcommit(self, context):
        # create port on the network controller
        port = self._prepare_port_for_controller(context)
        if port:
            self.servers.rest_create_port(port["network"]["tenant_id"],
                                          port["network"]["id"], port)

    def update_port_postcommit(self, context):
        # update port on the network controller
        port = self._prepare_port_for_controller(context)
        if port:
            self.servers.rest_update_port(port["network"]["tenant_id"],
                                          port["network"]["id"], port)

    def delete_port_postcommit(self, context):
        # delete port on the network controller
        port = context.current
        net = context.network.current
        self.servers.rest_delete_port(net["tenant_id"], net["id"], port['id'])

    def _prepare_port_for_controller(self, context):
        port = context.current
        net = context.network.current
        port['network'] = net
        port['binding_host'] = context._binding.host
        actx = ctx.get_admin_context()
        if (portbindings.HOST_ID in port and 'id' in port):
            host_id = port[portbindings.HOST_ID]
            porttracker_db.put_port_hostid(actx, port['id'], host_id)
        else:
            host_id = ''
        prepped_port = self._extend_port_dict_binding(actx, port)
        prepped_port = self._map_state_and_status(prepped_port)
        if (portbindings.HOST_ID not in prepped_port or
            prepped_port[portbindings.HOST_ID] == ''):
            # in ML2, controller doesn't care about ports without
            # the host_id set
            return False
        return prepped_port
