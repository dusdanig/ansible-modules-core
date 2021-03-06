#!/usr/bin/python
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#
DOCUMENTATION = """
---
module: nxos_template
version_added: "2.1"
author: "Peter sprygada (@privateip)"
short_description: Manage Cisco NXOS device configurations
description:
  - Manages network device configurations over SSH or NXAPI.  This module
    allows implementors to work with the device running-config.  It
    provides a way to push a set of commands onto a network device
    by evaluting the current running-config and only pushing configuration
    commands that are not already configured.  The config source can
    be a set of commands or a template.
extends_documentation_fragment: nxos
options:
  src:
    description:
      - The path to the config source.  The source can be either a
        file with config or a template that will be merged during
        runtime.  By default the task will search for the source
        file in role or playbook root folder in templates directory.
    required: false
    default: null
  force:
    description:
      - The force argument instructs the module to not consider the
        current devices running-config.  When set to true, this will
        cause the module to push the contents of I(src) into the device
        without first checking if already configured.
    required: false
    default: false
    choices: BOOLEANS
  include_defaults:
    description:
      - The module, by default, will collect the current device
        running-config to use as a base for comparision to the commands
        in I(src).  Setting this value to true will cause the module
        to issue the command `show running-config all` to include all
        device settings.
    required: false
    default: false
    choices: BOOLEANS
  backup:
    description:
      - When this argument is configured true, the module will backup
        the running-config from the node prior to making any changes.
        The backup file will be written to backup_{{ hostname }} in
        the root of the playbook directory.
    required: false
    default: false
    choices: BOOLEANS
  config:
    description:
      - The module, by default, will connect to the remote device and
        retrieve the current running-config to use as a base for comparing
        against the contents of source.  There are times when it is not
        desirable to have the task get the current running-config for
        every task in a playbook.  The I(config) argument allows the
        implementer to pass in the configuruation to use as the base
        config for comparision.
    required: false
    default: null
"""

EXAMPLES = """

- name: push a configuration onto the device
  nxos_template:
    src: config.j2

- name: forceable push a configuration onto the device
  nxos_template:
    src: config.j2
    force: yes

- name: provide the base configuration for comparision
  nxos_template:
    src: candidate_config.txt
    config: current_config.txt

"""

RETURN = """

commands:
  description: The set of commands that will be pushed to the remote device
  returned: always
  type: list
  sample: [...]

"""

def compare(this, other):
    parents = [item.text for item in this.parents]
    for entry in other:
        if this == entry:
            return None
    return this

def expand(obj, queue):
    block = [item.raw for item in obj.parents]
    block.append(obj.raw)

    current_level = queue
    for b in block:
        if b not in current_level:
            current_level[b] = collections.OrderedDict()
        current_level = current_level[b]
    for c in obj.children:
        if c.raw not in current_level:
            current_level[c.raw] = collections.OrderedDict()

def flatten(data, obj):
    for k, v in data.items():
        obj.append(k)
        flatten(v, obj)
    return obj

def get_config(module):
    config = module.params['config'] or dict()
    if not config and not module.params['force']:
        config = module.config
    return config

def main():

    argument_spec = dict(
        src=dict(),
        force=dict(default=False, type='bool'),
        include_defaults=dict(default=False, type='bool'),
        backup=dict(default=False, type='bool'),
        config=dict()
    )

    mutually_exclusive = [('config', 'backup'), ('config', 'force')]

    module = get_module(argument_spec=argument_spec,
                        mutually_exclusive=mutually_exclusive,
                        supports_check_mode=True)

    result = dict(changed=False)

    candidate = module.parse_config(module.params['src'])

    contents = get_config(module)
    result['_backup'] = contents
    config = module.parse_config(contents)

    commands = collections.OrderedDict()
    toplevel = [c.text for c in config]

    for line in candidate:
        if line.text.startswith('!') or line.text == '':
            continue

        if not line.parents:
            if line.text not in toplevel:
                expand(line, commands)
        else:
            item = compare(line, config)
            if item:
                expand(item, commands)

    commands = flatten(commands, list())

    if commands:
        if not module.check_mode:
            commands = [str(c).strip() for c in commands]
            response = module.configure(commands)
        result['changed'] = True

    result['commands'] = commands
    return module.exit_json(**result)

from ansible.module_utils.basic import *
from ansible.module_utils.urls import *
from ansible.module_utils.shell import *
from ansible.module_utils.netcfg import *
from ansible.module_utils.nxos import *
if __name__ == '__main__':
    main()
