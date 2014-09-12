# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 VMware Inc.
# All Rights Reserved
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

from neutron.openstack.common import log
from neutron.plugins.nicira.dbexts import nicira_db
from neutron.plugins.nicira import nsx_cluster
from neutron.plugins.nicira import NvpApiClient
from neutron.plugins.nicira import nvplib


LOG = log.getLogger(__name__)


def fetch_nsx_switches(session, cluster, neutron_net_id):
    """Retrieve logical switches for a neutron network.

    This function is optimized for fetching all the lswitches always
    with a single NSX query.
    If there is more than 1 logical switch (chained switches use case)
    NSX lswitches are queried by 'quantum_net_id' tag. Otherwise the NSX
    lswitch is directly retrieved by id (more efficient).
    """
    nsx_switch_ids = get_nsx_switch_ids(session, cluster, neutron_net_id)
    if len(nsx_switch_ids) > 1:
        lswitches = nvplib.get_lswitches(cluster, neutron_net_id)
    else:
        lswitches = [nvplib.get_lswitch_by_id(
            cluster, nsx_switch_ids[0])]
    return lswitches


def get_nsx_switch_ids(session, cluster, neutron_network_id):
    """Return the NSX switch id for a given neutron network.

    First lookup for mappings in Neutron database. If no mapping is
    found, query the NSX backend and add the mappings.
    """
    nsx_switch_ids = nicira_db.get_nsx_switch_ids(
        session, neutron_network_id)
    if not nsx_switch_ids:
        # Find logical switches from backend.
        # This is a rather expensive query, but it won't be executed
        # more than once for each network in Neutron's lifetime
        nsx_switches = nvplib.get_lswitches(cluster, neutron_network_id)
        if not nsx_switches:
            LOG.warn(_("Unable to find NSX switches for Neutron network %s"),
                     neutron_network_id)
            return
        nsx_switch_ids = []
        with session.begin(subtransactions=True):
            for nsx_switch in nsx_switches:
                nsx_switch_id = nsx_switch['uuid']
                nsx_switch_ids.append(nsx_switch_id)
                # Create DB mapping
                nicira_db.add_neutron_nsx_network_mapping(
                    session,
                    neutron_network_id,
                    nsx_switch_id)
    return nsx_switch_ids


def get_nsx_switch_and_port_id(session, cluster, neutron_port_id):
    """Return the NSX switch and port uuids for a given neutron port.

    First, look up the Neutron database. If not found, execute
    a query on NSX platform as the mapping might be missing because
    the port was created before upgrading to grizzly.

    This routine also retrieves the identifier of the logical switch in
    the backend where the port is plugged. Prior to Icehouse this
    information was not available in the Neutron Database. For dealing
    with pre-existing records, this routine will query the backend
    for retrieving the correct switch identifier.

    As of Icehouse release it is not indeed anymore possible to assume
    the backend logical switch identifier is equal to the neutron
    network identifier.
    """
    nvp_switch_id, nvp_port_id = nicira_db.get_nsx_switch_and_port_id(
        session, neutron_port_id)
    if not nvp_switch_id:
        # Find logical switch for port from backend
        # This is a rather expensive query, but it won't be executed
        # more than once for each port in Neutron's lifetime
        nvp_ports = nvplib.query_lswitch_lports(
            cluster, '*', relations='LogicalSwitchConfig',
            filters={'tag': neutron_port_id,
                     'tag_scope': 'q_port_id'})
        # Only one result expected
        # NOTE(salv-orlando): Not handling the case where more than one
        # port is found with the same neutron port tag
        if not nvp_ports:
            LOG.warn(_("Unable to find NVP port for Neutron port %s"),
                     neutron_port_id)
            # This method is supposed to return a tuple
            return None, None
        nvp_port = nvp_ports[0]
        nvp_switch_id = (nvp_port['_relations']
                         ['LogicalSwitchConfig']['uuid'])
        if nvp_port_id:
            # Mapping already exists. Delete before recreating
            nicira_db.delete_neutron_nsx_port_mapping(
                session, neutron_port_id)
        else:
            nvp_port_id = nvp_port['uuid']
        # (re)Create DB mapping
        nicira_db.add_neutron_nsx_port_mapping(
            session, neutron_port_id,
            nvp_switch_id, nvp_port_id)
    return nvp_switch_id, nvp_port_id


def create_nsx_cluster(cluster_opts, concurrent_connections, nsx_gen_timeout):
    cluster = nsx_cluster.NSXCluster(**cluster_opts)

    def _ctrl_split(x, y):
        return (x, int(y), True)

    api_providers = [_ctrl_split(*ctrl.split(':'))
                     for ctrl in cluster.nsx_controllers]
    cluster.api_client = NvpApiClient.NVPApiHelper(
        api_providers, cluster.nsx_user, cluster.nsx_password,
        request_timeout=cluster.req_timeout,
        http_timeout=cluster.http_timeout,
        retries=cluster.retries,
        redirects=cluster.redirects,
        concurrent_connections=concurrent_connections,
        nvp_gen_timeout=nsx_gen_timeout)
    return cluster


def get_nsx_router_id(session, cluster, neutron_router_id):
    """Return the NSX router uuid for a given neutron router.

    First, look up the Neutron database. If not found, execute
    a query on NSX platform as the mapping might be missing.
    """
    nsx_router_id = nicira_db.get_nsx_router_id(
        session, neutron_router_id)
    if not nsx_router_id:
        # Find logical router from backend.
        # This is a rather expensive query, but it won't be executed
        # more than once for each router in Neutron's lifetime
        nsx_routers = nvplib.query_lrouters(
            cluster, '*',
            filters={'tag': neutron_router_id,
                     'tag_scope': 'q_router_id'})
        # Only one result expected
        # NOTE(salv-orlando): Not handling the case where more than one
        # port is found with the same neutron port tag
        if not nsx_routers:
            LOG.warn(_("Unable to find NSX router for Neutron router %s"),
                     neutron_router_id)
            return
        nsx_router = nsx_routers[0]
        nsx_router_id = nsx_router['uuid']
        with session.begin(subtransactions=True):
            # Create DB mapping
            nicira_db.add_neutron_nsx_router_mapping(
                session,
                neutron_router_id,
                nsx_router_id)
    return nsx_router_id
