# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 OpenStack Foundation
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

"""Add support for SSL-VPN

Revision ID: 50cf41b71c2d
Revises: 4ca36cfc898c
Create Date: 2013-12-06 12:13:54.893327

"""

# revision identifiers, used by Alembic.
revision = '50cf41b71c2d'
down_revision = '4ca36cfc898c'

# Change to ['*'] if this migration applies to all plugins

migration_for_plugins = [
    'neutron.services.vpn.plugin.VPNDriverPlugin'
]

from alembic import op
import sqlalchemy as sa

from neutron.db import migration


def upgrade(active_plugins=None, options=None):
    if not migration.should_run(active_plugins, migration_for_plugins):
        return

    op.create_table(
        'vpncredentials',
        sa.Column('tenant_id', sa.String(length=255), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('ca', sa.Text(), nullable=False),
        sa.Column('server_certificate', sa.Text(), nullable=False),
        sa.Column('server_key', sa.Text(), nullable=False),
        sa.Column('dh', sa.Text(), nullable=True),
        sa.Column('crl', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'ssl_vpn_connections',
        sa.Column('tenant_id', sa.String(length=255), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('admin_state_up', sa.Boolean(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('vpnservice_id', sa.String(length=36), nullable=False),
        sa.Column('credential_id', sa.String(length=36), nullable=False),
        sa.Column(
            'client_address_pool_cidr', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['vpnservice_id'], ['vpnservices.id'], ),
        sa.ForeignKeyConstraint(['credential_id'], ['vpncredentials.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade(active_plugins=None, options=None):
    if not migration.should_run(active_plugins, migration_for_plugins):
        return
    op.drop_table('ssl_vpn_connections')
    op.drop_table('vpncredentials')
