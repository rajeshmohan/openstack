# vim: tabstop=4 shiftwidth=4 softtabstop=4
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
import mock

from neutron.openstack.common import uuidutils
from neutron.plugins.common import constants
from neutron.services.vpn.device_drivers import ipsec as ipsec_driver
from neutron.tests.unit.services.vpn import device_drivers as driver_test

_uuid = uuidutils.generate_uuid


class TestIPsecDeviceDriver(driver_test.BaseDeviceDriverTestCase):
    FAKE_ROUTER_ID = _uuid()
    FAKE_VPN_SERVICE = {
        'id': _uuid(),
        'router_id': FAKE_ROUTER_ID,
        'admin_state_up': True,
        'status': constants.PENDING_CREATE,
        'subnet': {'cidr': '10.0.0.0/24'},
        'ipsec_site_connections': [
            {'peer_cidrs': ['20.0.0.0/24',
                            '30.0.0.0/24']},
            {'peer_cidrs': ['40.0.0.0/24',
                            '50.0.0.0/24']}]
    }

    def setUp(self, driver=ipsec_driver.OpenSwanDriver):
        super(TestIPsecDeviceDriver, self).setUp(driver, [
            'os.makedirs',
            'os.path.isdir',
            'neutron.agent.linux.utils.replace_file',
            'neutron.openstack.common.rpc.create_connection',
            'neutron.services.vpn.device_drivers.ipsec.'
            'OpenSwanProcess._gen_config_content',
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
        self.agent.assert_has_calls([
            mock.call.add_nat_rule(
                self.FAKE_ROUTER_ID,
                'POSTROUTING',
                '-s 10.0.0.0/24 -d 20.0.0.0/24 -m policy '
                '--dir out --pol ipsec -j ACCEPT ',
                top=True),
            mock.call.add_nat_rule(
                self.FAKE_ROUTER_ID,
                'POSTROUTING',
                '-s 10.0.0.0/24 -d 30.0.0.0/24 -m policy '
                '--dir out --pol ipsec -j ACCEPT ',
                top=True),
            mock.call.add_nat_rule(
                self.FAKE_ROUTER_ID,
                'POSTROUTING',
                '-s 10.0.0.0/24 -d 40.0.0.0/24 -m policy '
                '--dir out --pol ipsec -j ACCEPT ',
                top=True),
            mock.call.add_nat_rule(
                self.FAKE_ROUTER_ID,
                'POSTROUTING',
                '-s 10.0.0.0/24 -d 50.0.0.0/24 -m policy '
                '--dir out --pol ipsec -j ACCEPT ',
                top=True),
            mock.call.iptables_apply(self.FAKE_ROUTER_ID)
        ])
        process.update.assert_called_once_with()
        self.driver.agent_rpc.update_status.assert_called_once_with(
            context,
            [{'status': 'ACTIVE',
             'ipsec_site_connections': {},
             'updated_pending_status': True,
             'id': self.FAKE_VPN_SERVICE['id']}])
