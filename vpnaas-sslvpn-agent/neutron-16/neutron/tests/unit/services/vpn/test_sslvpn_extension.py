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

import copy

import mock
from oslo.config import cfg
from webob import exc
import webtest

from neutron.api import extensions
from neutron.api.v2 import attributes
from neutron.common import config
from neutron.extensions import sslvpn
from neutron import manager
from neutron.openstack.common import uuidutils
from neutron.plugins.common import constants
from neutron import quota
from neutron.tests.unit import test_api_v2
from neutron.tests.unit import test_extensions
from neutron.tests.unit import testlib_api


_uuid = uuidutils.generate_uuid
_get_path = test_api_v2._get_path


class SslvpnTestExtensionManager(object):

    def get_resources(self):
        # Add the resources to the global attribute map
        # This is done here as the setup process won't
        # initialize the main API router which extends
        # the global attribute map
        attributes.RESOURCE_ATTRIBUTE_MAP.update(
            sslvpn.RESOURCE_ATTRIBUTE_MAP)
        return sslvpn.Sslvpn.get_resources()

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []


class SslvpnExtensionTestCase(testlib_api.WebTestCase):
    fmt = 'json'

    def setUp(self):
        super(SslvpnExtensionTestCase, self).setUp()
        plugin = 'neutron.extensions.sslvpn.SSLVPNPluginBase'
        # Ensure 'stale' patched copies of the plugin are never returned
        manager.NeutronManager._instance = None

        # Ensure existing ExtensionManager is not used
        extensions.PluginAwareExtensionManager._instance = None

        # Create the default configurations
        args = ['--config-file', test_api_v2.etcdir('neutron.conf.test')]
        config.parse(args)

        #just stubbing core plugin with LoadBalancer plugin
        cfg.CONF.set_override('core_plugin', plugin)
        cfg.CONF.set_override('service_plugins', [plugin])

        self._plugin_patcher = mock.patch(plugin, autospec=True)
        self.plugin = self._plugin_patcher.start()
        instance = self.plugin.return_value
        instance.get_plugin_type.return_value = constants.VPN

        ext_mgr = SslvpnTestExtensionManager()
        self.ext_mdw = test_extensions.setup_extensions_middleware(ext_mgr)
        self.api = webtest.TestApp(self.ext_mdw)
        super(SslvpnExtensionTestCase, self).setUp()

        quota.QUOTAS._driver = None
        cfg.CONF.set_override('quota_driver', 'neutron.quota.ConfDriver',
                              group='QUOTAS')

    def tearDown(self):
        self._plugin_patcher.stop()
        self.api = None
        self.plugin = None
        cfg.CONF.reset()
        super(SslvpnExtensionTestCase, self).tearDown()

    def test_ssl_vpn_connection_create(self):
        """Test case to create an ssl_vpn_connection."""
        conn_id = _uuid()
        data = {'ssl_vpn_connection': {
            'name': 'conn1',
            'client_address_pool_cidr': '192.168.0.0/24',
            'credential_id': _uuid(),
            'admin_state_up': True,
            'vpnservice_id': _uuid(),
            'tenant_id': _uuid()}}

        return_value = copy.copy(data['ssl_vpn_connection'])
        return_value.update({'id': conn_id})

        instance = self.plugin.return_value
        instance.create_ssl_vpn_connection.return_value = return_value
        res = self.api.post(_get_path('vpn/ssl-vpn-connections', fmt=self.fmt),
                            self.serialize(data),
                            content_type='application/%s' % self.fmt)
        instance.create_ssl_vpn_connection.assert_called_with(
            mock.ANY, ssl_vpn_connection=data)
        self.assertEqual(res.status_int, exc.HTTPCreated.code)
        res = self.deserialize(res)
        self.assertIn('ssl_vpn_connection', res)
        self.assertEqual(res['ssl_vpn_connection'], return_value)

    def test_ssl_vpn_connection_list(self):
        """Test case to list all ssl vpn connections."""
        conn_id = _uuid()

        return_value = [{'name': 'conn1',
                         'client_address_pool_cidr': '192.168.0.0/24',
                         'credential_id': _uuid(),
                         'admin_state_up': True,
                         'vpnservice_id': _uuid(),
                         'tenant_id': _uuid(),
                         'id': conn_id}]
        instance = self.plugin.return_value
        instance.get_ssl_vpn_connections.return_value = return_value

        res = self.api.get(_get_path('vpn/ssl-vpn-connections', fmt=self.fmt))

        instance.get_ssl_vpn_connections.assert_called_with(
            mock.ANY, fields=mock.ANY, filters=mock.ANY)
        self.assertEqual(res.status_int, exc.HTTPOk.code)

    def test_ssl_vpn_connection_update(self):
        """Test case to update an ssl_vpn_connection."""
        conn_id = _uuid()
        conn_data = {'name': 'conn2',
                     'admin_state_up': False}
        update_data = {'ssl_vpn_connection': conn_data}
        return_value = {'name': 'conn2',
                        'client_address_pool_cidr': '192.168.1.0/24',
                        'credential_id': _uuid(),
                        'admin_state_up': True,
                        'vpnservice_id': _uuid(),
                        'tenant_id': _uuid(),
                        'id': conn_id}

        instance = self.plugin.return_value
        instance.update_ssl_vpn_connection.return_value = return_value

        res = self.api.put(_get_path('vpn/ssl-vpn-connections', id=conn_id,
                                     fmt=self.fmt),
                           self.serialize(update_data))

        instance.update_ssl_vpn_connection.assert_called_with(
            mock.ANY, conn_id, ssl_vpn_connection=update_data)
        self.assertEqual(res.status_int, exc.HTTPOk.code)
        res = self.deserialize(res)
        self.assertIn('ssl_vpn_connection', res)
        self.assertEqual(res['ssl_vpn_connection'], return_value)

    def test_ssl_vpn_connection_get(self):
        """Test case to get or show an ssl_vpn_connection."""
        conn_id = _uuid()
        return_value = {'name': 'conn2',
                        'client_address_pool_cidr': '192.168.1.0/24',
                        'credential_id': _uuid(),
                        'admin_state_up': True,
                        'vpnservice_id': _uuid(),
                        'tenant_id': _uuid(),
                        'id': conn_id}

        instance = self.plugin.return_value
        instance.get_ssl_vpn_connection.return_value = return_value

        res = self.api.get(_get_path('vpn/ssl-vpn-connections', id=conn_id,
                                     fmt=self.fmt))

        instance.get_ssl_vpn_connection.assert_called_with(mock.ANY,
                                                           conn_id,
                                                           fields=mock.ANY)
        self.assertEqual(res.status_int, exc.HTTPOk.code)
        res = self.deserialize(res)
        self.assertIn('ssl_vpn_connection', res)
        self.assertEqual(res['ssl_vpn_connection'], return_value)

    def test_ssl_vpn_connection_delete(self):
        """Test case to delete an ssl_vpn_connection."""
        conn_id = _uuid()
        res = self.api.delete(_get_path('vpn/ssl-vpn-connections',
                                        id=conn_id,
                                        fmt=self.fmt))
        instance = self.plugin.return_value
        instance.delete_ssl_vpn_connection.assert_called_with(
            mock.ANY, conn_id)
        self.assertEqual(res.status_int, exc.HTTPNoContent.code)


class SslvpnExtensionTestCaseXML(SslvpnExtensionTestCase):
    fmt = 'xml'
