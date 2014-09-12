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
import contextlib
import hashlib
import logging
import os
import webob.exc

from neutron.api.extensions import ExtensionMiddleware
from neutron.api.extensions import PluginAwareExtensionManager
from neutron.common import config
import neutron.extensions
from neutron.extensions import sslvpn
from neutron.extensions import vpnaas
from neutron.extensions import vpncredential
from neutron.plugins.common import constants
from neutron.tests.unit.db.vpn import test_db_vpnaas
from neutron.tests.unit import test_db_plugin

LOG = logging.getLogger(__name__)

DB_CORE_PLUGIN_KLASS = 'neutron.db.db_base_plugin_v2.NeutronDbPluginV2'
DB_VPN_PLUGIN_KLASS = "neutron.tests.unit.db.vpn.test_db_vpnaas.TestVPNPlugin"
ROOTDIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__),
    '..', '..', '..', '..'))
ETCDIR = os.path.join(ROOTDIR, 'etc')

extensions_path = ':'.join(neutron.extensions.__path__)


def etcdir(*p):
    return os.path.join(ETCDIR, *p)


RESOURCE_ATTRIBUTE_MAP = sslvpn.RESOURCE_ATTRIBUTE_MAP.copy()
RESOURCE_ATTRIBUTE_MAP.update(vpnaas.RESOURCE_ATTRIBUTE_MAP)
RESOURCE_ATTRIBUTE_MAP.update(vpncredential.RESOURCE_ATTRIBUTE_MAP)


class SSLVPNPluginDbTestCase(test_db_vpnaas.VPNPluginDbTestCase):
    resource_prefix_map = dict(
        (k.replace('_', '-'),
         constants.COMMON_PREFIXES[constants.VPN])
        for k in RESOURCE_ATTRIBUTE_MAP)

    def setUp(self, core_plugin=None, vpnaas_plugin=DB_VPN_PLUGIN_KLASS):
        service_plugins = {'vpnaas_plugin': vpnaas_plugin}
        plugin_str = ('neutron.tests.unit.db.vpn.'
                      'test_db_vpnaas.TestVpnCorePlugin')
        super(test_db_vpnaas.VPNPluginDbTestCase, self).setUp(
            plugin_str,
            service_plugins=service_plugins
        )
        self._subnet_id = "0c798ed8-33ba-11e2-8b28-000c291c4d14"
        self.core_plugin = test_db_vpnaas.TestVpnCorePlugin
        self.plugin = test_db_vpnaas.TestVPNPlugin()
        ext_mgr = PluginAwareExtensionManager(
            extensions_path,
            {constants.CORE: self.core_plugin,
             constants.VPN: self.plugin,
             constants.SSLVPN: self.plugin,
             constants.VPNCREDENTIAL: self.plugin}
        )
        app = config.load_paste_app('extensions_test_app')
        self.ext_api = ExtensionMiddleware(app, ext_mgr=ext_mgr)

    def _create_ssl_vpn_connection(self, fmt, name, credential_id,
                                   client_address_pool_cidr,
                                   vpnservice_id, expected_res_status=None,
                                   **kwargs):
        data = {'ssl_vpn_connection': {
            'name': name,
            'credential_id': credential_id,
            'vpnservice_id': vpnservice_id,
            'tenant_id': self._tenant_id,
            'client_address_pool_cidr': client_address_pool_cidr
        }}

        data['ssl_vpn_connection'].update(kwargs)

        req = self.new_create_request('ssl-vpn-connections', data, fmt)
        res = req.get_response(self.ext_api)
        if expected_res_status:
            self.assertEqual(res.status_int, expected_res_status)

        return res

    @contextlib.contextmanager
    def ssl_vpn_connection(self, name='fake_name',
                           client_address_pool_cidr='10.0.0.0/24',
                           fmt=None,
                           no_delete=False,
                           vpnservice=None,
                           **kwargs):
        if not fmt:
            fmt = self.fmt
        with contextlib.nested(
            test_db_plugin.optional_ctx(vpnservice, self.vpnservice),
            self.vpn_credential()) as (
                vpnservice, vpn_credential):
            res = self._create_ssl_vpn_connection(
                fmt,
                name,
                credential_id=vpn_credential['vpn_credential']['id'],
                vpnservice_id=vpnservice['vpnservice']['id'],
                client_address_pool_cidr=client_address_pool_cidr,
                **kwargs)
            if res.status_int >= 400:
                raise webob.exc.HTTPClientError(
                    explanation=_("Unexpected error code: %s") %
                    res.status_int
                )
            try:
                ssl_vpn_connection = self.deserialize(fmt, res)
                yield ssl_vpn_connection
            finally:
                if not no_delete:
                    self._delete(
                        'ssl-vpn-connections',
                        ssl_vpn_connection['ssl_vpn_connection']['id'],
                        expected_code=webob.exc.HTTPNoContent.code
                    )

    def _create_vpn_credential(
        self,
        fmt,
        ca,
        server_certificate,
        server_key,
        dh,
        crl,
        expected_res_status=None,
        **kwargs
    ):
        data = {'vpn_credential': {
            'ca': ca,
            'server_certificate': server_certificate,
            'server_key': server_key,
            'dh': dh,
            'crl': crl,
            'tenant_id': self._tenant_id
        }}

        data['vpn_credential'].update(kwargs)

        req = self.new_create_request('vpn-credentials', data, fmt)
        res = req.get_response(self.ext_api)
        if expected_res_status:
            self.assertEqual(res.status_int, expected_res_status)

        return res

    @contextlib.contextmanager
    def vpn_credential(self, ca='fake_ca',
                       server_certificate='fake_certificate',
                       server_key='fake_key',
                       dh='fake_dh', crl='fake_crl', no_delete=False,
                       fmt=None, **kwargs):
        if not fmt:
            fmt = self.fmt
        res = self._create_vpn_credential(
            fmt,
            ca=ca,
            server_certificate=server_certificate,
            server_key=server_key,
            dh=dh,
            crl=crl,
            **kwargs)
        if res.status_int >= 400:
            raise webob.exc.HTTPClientError(
                explanation=_("Unexpected error code: %s") %
                res.status_int
            )
        try:
            vpn_credential = self.deserialize(fmt, res)
            yield vpn_credential
        finally:
            if not no_delete:
                self._delete(
                    'vpn-credentials',
                    vpn_credential['vpn_credential']['id'],
                    expected_code=webob.exc.HTTPNoContent.code
                )


class TestSSLVPN(SSLVPNPluginDbTestCase):

    def test_create_ssl_vpn_connection(self, **extras):
        expected = {
            'name': 'fake_name',
            'client_address_pool_cidr': '10.0.0.0/24'
        }
        expected.update(extras)

        with self.ssl_vpn_connection(
            **extras
        ) as ssl_vpn_connection:
            self.assertEqual(
                dict((k, v)
                     for k, v
                     in ssl_vpn_connection['ssl_vpn_connection'].items()
                     if k in expected),
                expected
            )
        return ssl_vpn_connection

    def test_show_ssl_vpn_connection(self):
        keys = {
            'name': 'fake_name',
            'client_address_pool_cidr': '10.0.0.0/24'
        }
        with self.ssl_vpn_connection(**keys) as ssl_vpn_connection:
            req = self.new_show_request(
                'ssl-vpn-connections',
                ssl_vpn_connection['ssl_vpn_connection']['id']
            )
            res = self.deserialize(self.fmt, req.get_response(self.ext_api))
            for k, v in keys.iteritems():
                self.assertEqual(res['ssl_vpn_connection'][k], v)

    def test_list_ssl_vpn_connection(self):
        keys = {
            'name': 'fake_name',
            'client_address_pool_cidr': '10.0.0.0/24'
        }
        with self.ssl_vpn_connection(**keys):
            req = self.new_list_request(
                'ssl-vpn-connections'
            )
            res = self.deserialize(self.fmt, req.get_response(self.ext_api))
            self.assertEqual(len(res), 1)
            for k, v in keys.iteritems():
                self.assertEqual(res['ssl_vpn_connections'][0][k], v)

    def test_delete_ssl_vpn_connection(self):
        with self.ssl_vpn_connection(no_delete=True) as ssl_vpn_connection:
            req = self.new_delete_request(
                'ssl-vpn-connections',
                ssl_vpn_connection['ssl_vpn_connection']['id']
            )
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, webob.exc.HTTPNoContent.code)

    def test_create_vpn_credential(self, **extras):
        expected = {
            'ca': 'fake_ca',
            'server_certificate': 'fake_certificate',
            'server_key': 'fake_key',
            'dh': 'fake_dh',
            'crl': 'fake_crl'
        }
        expected.update(extras)

        with self.vpn_credential(
            fmt=self.fmt,
            **expected
        ) as vpn_credential:
            expected['server_key'] = hashlib.sha256(
                expected['server_key']).hexdigest()
            self.assertEqual(
                dict((k, v)
                     for k, v
                     in vpn_credential['vpn_credential'].items()
                     if k in expected),
                expected
            )
        return vpn_credential

    def test_show_vpn_credential(self):
        keys = {
            'ca': 'fake_ca',
            'server_certificate': 'fake_certificate',
            'server_key': 'fake_key',
            'dh': 'fake_dh',
            'crl': 'fake_crl'
        }
        with self.vpn_credential(**keys) as vpn_credential:
            req = self.new_show_request(
                'vpn-credentials',
                vpn_credential['vpn_credential']['id']
            )
            res = self.deserialize(self.fmt, req.get_response(self.ext_api))
            keys['server_key'] = hashlib.sha256(keys['server_key']).hexdigest()
            for k, v in keys.iteritems():
                self.assertEqual(res['vpn_credential'][k], v)

    def test_list_vpn_credential(self):
        keys = {
            'ca': 'fake_ca',
            'server_certificate': 'fake_certificate',
            'server_key': 'fake_key',
            'dh': 'fake_dh',
            'crl': 'fake_crl'
        }
        with self.vpn_credential(**keys):
            req = self.new_list_request(
                'vpn-credentials'
            )
            res = self.deserialize(self.fmt, req.get_response(self.ext_api))
            self.assertEqual(len(res), 1)
            keys['server_key'] = hashlib.sha256(keys['server_key']).hexdigest()
            for k, v in keys.iteritems():
                self.assertEqual(res['vpn_credentials'][0][k], v)

    def test_delete_vpn_credential(self):
        with self.vpn_credential(no_delete=True) as vpn_credential:
            req = self.new_delete_request(
                'vpn-credentials',
                vpn_credential['vpn_credential']['id']
            )
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, webob.exc.HTTPNoContent.code)
