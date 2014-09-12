# Copyright 2014 OpenStack Foundation
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

"""service insertion in FWaaS

Revision ID: 5608d8f235ea
Revises: 1e5dd1d09b22
Create Date: 2014-01-08 17:51:22.961220

"""

# revision identifiers, used by Alembic.
revision = '5608d8f235ea'
down_revision = '1e5dd1d09b22'

# Change to ['*'] if this migration applies to all plugins

migration_for_plugins = [
    'neutron.services.firewall.fwaas_plugin.FirewallPlugin',
]

from alembic import op
import sqlalchemy as sa

from neutron.db import migration


def upgrade(active_plugins=None, options=None):
    if not migration.should_run(active_plugins, migration_for_plugins):
        return

    op.create_table('service_context',
                    sa.Column('id', sa.String(length=36), nullable=False),
                    sa.PrimaryKeyConstraint('id'),
                    mysql_engine='InnoDB')
    op.create_table('si_network_contexts',
                    sa.Column('id', sa.String(length=36), nullable=False),
                    sa.Column('service_context_id', sa.String(length=36),
                              nullable=False),
                    sa.Column('network_id', sa.String(length=36),
                              nullable=False),
                    sa.ForeignKeyConstraint(['network_id'], ['networks.id'],
                                            ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['service_context_id'],
                                            ['service_context.id'],
                                            ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    mysql_engine='InnoDB')
    op.create_table('si_port_contexts',
                    sa.Column('id', sa.String(length=36), nullable=False),
                    sa.Column('service_context_id', sa.String(length=36),
                              nullable=False),
                    sa.Column('port_id', sa.String(length=36), nullable=False),
                    sa.ForeignKeyConstraint(['port_id'], ['ports.id'],
                                            ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['service_context_id'],
                                            ['service_context.id'],
                                            ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    mysql_engine='InnoDB')
    op.create_table('si_subnet_contexts',
                    sa.Column('id', sa.String(length=36), nullable=False),
                    sa.Column('service_context_id', sa.String(length=36),
                              nullable=False),
                    sa.Column('subnet_id', sa.String(length=36),
                              nullable=False),
                    sa.ForeignKeyConstraint(['service_context_id'],
                                            ['service_context.id'],
                                            ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['subnet_id'], ['subnets.id'],
                                            ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    mysql_engine='InnoDB')
    op.create_table('si_router_contexts',
                    sa.Column('id', sa.String(length=36), nullable=False),
                    sa.Column('service_context_id', sa.String(length=36),
                              nullable=False),
                    sa.Column('router_id', sa.String(length=36),
                              nullable=False),
                    sa.ForeignKeyConstraint(['router_id'], ['routers.id'],
                                            ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['service_context_id'],
                                            ['service_context.id'],
                                            ondelete='CASCADE'),
                    sa.PrimaryKeyConstraint('id'),
                    mysql_engine='InnoDB')
    op.add_column('firewalls',
                  sa.Column('service_context_id', sa.String(length=36),
                            nullable=True))
    op.create_unique_constraint(None, 'firewalls', ['service_context_id'])
    ### end Alembic commands ###


def downgrade(active_plugins=None, options=None):
    if not migration.should_run(active_plugins, migration_for_plugins):
        return

    op.drop_column('firewalls', 'service_context_id')
    op.drop_table('si_router_contexts')
    op.drop_table('si_subnet_contexts')
    op.drop_table('si_port_contexts')
    op.drop_table('si_network_contexts')
    op.drop_table('service_context')
    ### end Alembic commands ###
