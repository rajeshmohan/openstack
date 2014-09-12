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
import mock

from neutron.openstack.common import uuidutils
from neutron.plugins.common import constants
from neutron.services.vpn.device_drivers import sslvpn as sslvpn_driver
from neutron.tests.unit.services.vpn import device_drivers as driver_test

_uuid = uuidutils.generate_uuid


class TestSSLVPNDeviceDriver(driver_test.BaseDeviceDriverTestCase):
    FAKE_ROUTER_ID = _uuid()
    FAKE_VPN_SERVICE = {
        'id': _uuid(),
        'router_id': FAKE_ROUTER_ID,
        'admin_state_up': True,
        'status': constants.PENDING_CREATE,
        'subnet': {'cidr': '10.0.0.0/24'},
        'ssl_vpn_connections': [
            {'id': _uuid(),
             'client_address_pool_cidr': '100.0.0.0/24'}]
    }

    def setUp(self, driver=sslvpn_driver.OpenVPNDriver):
        super(TestSSLVPNDeviceDriver, self).setUp(driver, [
            'os.makedirs',
            'os.path.isdir',
            'neutron.agent.linux.utils.replace_file',
            'neutron.openstack.common.rpc.create_connection',
            'neutron.services.vpn.device_drivers.sslvpn.'
            'OpenVPNProcess._gen_config_content',
            'os.remove',
            'shutil.rmtree',
        ])

    def test_sync_added(self):
        self.driver.agent_rpc.get_vpn_services_on_host.return_value = [
            self.FAKE_VPN_SERVICE]
        context = mock.Mock()
        process = mock.Mock()
        process.vpnservice = self.FAKE_VPN_SERVICE
        process.connection_status = {}
        process.status = constants.ACTIVE
        process.updated_pending_status = True
        self.driver.process_status_cache = {}
        self.driver.processes = {
            self.FAKE_ROUTER_ID: process}
        self.driver.sync(context, [])
        process.update.assert_called_once_with()
        self.driver.agent_rpc.update_status.assert_called_once_with(
            context,
            [{'status': 'ACTIVE',
             'ssl_vpn_connections': {},
             'updated_pending_status': True,
             'id': self.FAKE_VPN_SERVICE['id']}])
