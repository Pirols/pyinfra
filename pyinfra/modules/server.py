# pyinfra
# File: pyinfra/modules/server.py
# Desc: the base os-level module

'''
The server module takes care of os-level state. Targets POSIX compatability, tested on Linux/BSD.

Uses POSIX commands:

+ `echo`, `cat`
+ `hostname`, `uname`
+ `useradd`, `userdel`, `usermod`
'''

from hashlib import sha1

from pyinfra import host
from pyinfra.api import operation, operation_facts

from . import files


@operation
def wait(port=None):
    '''
    Waits for a port to come active on the target machine. Requires either netcat to be installed
    or timeout & bash with magic sockets (/dev/tcp).

    Will error if these are not present - works on all tested targets (see docs/README.md).
    '''
    return ['''
        if [ $(which nc) ]; then
            while ! nc -q 1 localhost {0} < /dev/null; do sleep 5; done
        elif [ $(which timeout) ] && [ $(which bash) ]; then
            while ! timeout 1 bash -c "echo > /dev/tcp/localhost/{0}"; do sleep 5; done
        else
            echo "No nc or timeout/bash!"
            exit 1
        fi
    '''.format(port)]


@operation
def shell(*commands):
    '''Run raw shell code.'''
    return list(commands)


@operation
def script(filename):
    '''Upload and execute a local script on the remote host.'''
    commands = []

    hash_ = sha1()
    hash_.update(filename)
    temp_file = '/tmp/{0}'.format(hash_.hexdigest())

    commands.extend(files.put(filename, temp_file))

    commands.append('chmod +x {0}'.format(temp_file))
    commands.append(temp_file)

    return commands


@operation
@operation_facts('users')
def user(name, present=True, home=None, shell=None, public_keys=None):
    '''
    Manage Linux users & their ssh `authorized_keys`.

    # public_keys: list of public keys to attach to this user
    '''
    commands = []
    users = host.users or {}
    user = users.get(name)

    # User exists but we don't want them?
    if not present and user:
        commands.append('userdel {0}'.format(name))
        return commands

    # User doesn't exist but we want them?
    if present and user is None:
        # Create the user w/home/shell
        commands.append('useradd -d {0} -s {1} {2}'.format(home, shell, name))

    # User exists and we want them, check home/shell/keys
    else:
        # Check homedir
        if user['home'] != home:
            commands.append('usermod -d {0} {1}'.format(home, name))

        # Check shell
        if user['shell'] != shell:
            commands.append('usermod -s {0} {1}'.format(shell, name))

    # Ensure home directory ownership
    commands.extend(files.directory(
        home,
        user=name,
        group=name
    ))

    # Add SSH keys
    if public_keys is not None:
        # Ensure .ssh directory
        # note that this always outputs commands unless the SSH user has access to the
        # authorized_keys file, ie the SSH user is the user defined in this function
        commands.extend(files.directory(
            '{0}/.ssh'.format(home),
            user=name,
            group=name,
            mode='700'
        ))

        filename = '{0}/.ssh/authorized_keys'.format(home)

        # Ensure authorized_keys
        commands.extend(file(
            filename,
            user=name,
            group=name,
            mode='600'
        ))

        for key in public_keys:
            commands.append('cat {0} | grep "{1}" || echo "{1}" >> {0}'.format(filename, key))

    return commands
