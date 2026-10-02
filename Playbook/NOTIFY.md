# Deploy notify with Ansible

Run from a Linux/WSL/macOS Ansible controller with this repository checked out.
The playbook uses the existing `linux` inventory group and sudo (`become`).
Targets need an existing desktop account and Python usable by Ansible. No extra
Ansible collections are needed for the Debian/Ubuntu hosts in this inventory.
Red Hat/Fedora and Arch package mappings are included too; Arch's package backend
requires `community.general` on the controller.

From the repository root:

```sh
cd Playbook
export ANSIBLE_CONFIG="$PWD/ansible.cfg"
ansible-playbook deploy_notify.yml --limit ubuntu1
```

Select the configuration explicitly: Ansible ignores an automatically discovered
`ansible.cfg` when the working directory is writable by everyone, which can
happen in Windows/WSL checkouts. This configuration selects `inventory.ini`.

This installs a **receive-only** `/usr/local/bin/notify` and its dependencies and
configures background startup at graphical login. It also tries to start the
receiver immediately for an active desktop session. Deployed copies support only `listen` and
`autostart`; `send`, `all`, and `keygen` are unavailable, and sender code is not
included. The controller keeps the full `Notify/notify` program for sending.
No keys are required by default. The default
desktop user is the inventory's `ansible_user` (`sysadmin` in this inventory).
If another account logs into the desktop, specify it:

```sh
ansible-playbook deploy_notify.yml --limit 10.1.1.10 -e notify_user=alice
```

Use `--limit 'ubuntu1:ubuntu2'` for both desktop groups. Omit `--limit` to target
the entire `linux` group, including its server groups. Only hosts with a graphical
desktop and notification service can display pop-ups. Add `-K` if sudo requires
a password that is not already configured in the inventory.

The playbook enables background startup at each graphical login and, by default,
tries to start a background receiver immediately. Over SSH it reads the
configured user's desktop environment from their systemd user manager. If no
desktop environment is available, it reports that startup will happen at the next
graphical login. No open terminal is required once the background receiver starts.
To start manually, run `notify listen --background` in the target user's desktop
terminal. The playbook prints the full command if you selected a custom key path,
host, or port. Startup output is logged to
`~/.config/notify/receiver.log` on the target (under `notify_config_home` if
customized). If updating an
already running receiver, restart it or log out/in to load the new program,
settings, or key. Do not run two listeners on the same address and port.

To update machines deployed with the old full program, rerun this playbook with
the same host selection and authentication settings. It replaces the installed
executable with the receiver-only build; restart existing listeners or log out/in.

## Sending

From the `Playbook` directory on the controller:

```sh
python3 ../Notify/notify send 10.1.1.10 "Hello from Ansible's controller!"
python3 ../Notify/notify all '10.1-13.1.(10,20,30,40)' "Meeting soon" --title Reminder
```

Each receiver must be running. Failed targets are skipped and delivery continues;
the final summary reports how many targets accepted the notification. See
[`Notify/README.md`](../Notify/README.md) for range and list syntax.

Allow inbound TCP **8765** from the sender's address in the receiving machine's
firewall. The playbook does not change firewall rules. Use a trusted LAN or VPN;
without authentication, any machine able to reach the listener can send pop-ups.
Message contents are not encrypted.

Receive-only deployment limits the installed Notify program, not other programs
on that machine. To restrict network senders to the controller, configure receiver
firewalls to allow the notification port only from the controller. Shared-key
authentication alone does not separate sender and receiver permissions: a user
who can read a receiver's key can use it with a separate client to send messages.

## Optional shared key

Set `-e notify_auth=true` to enable shared-key authentication for deployed
receivers. With this option enabled:

The first run generates a key on the controller at `~/.config/notify/key`
(`$XDG_CONFIG_HOME/notify/key` if set). Later runs reuse it. All targeted
receivers receive that same key in the selected desktop user's configuration
directory. Existing receiver keys are replaced with the controller's key.
Keep the controller key to continue sending messages and deploying more hosts.
Key contents are hidden from Ansible output and diffs.

From the `Playbook` directory on that controller:

```sh
python3 ../Notify/notify send 10.1.1.10 "Hello from Ansible's controller!" --key-file ~/.config/notify/key
python3 ../Notify/notify all '10.1-13.1.10' "Meeting soon" --key-file ~/.config/notify/key
```

Senders must explicitly supply `--key-file` with the same shared key; use your
custom controller key path if configured. Existing listeners retain their loaded
authentication settings until restarted.

## Settings

Set these with `-e`, `host_vars`, or `group_vars` as appropriate:

| Variable | Default | Purpose |
| --- | --- | --- |
| `notify_user` | `ansible_user` | Existing account whose desktop receives pop-ups. |
| `notify_host` | `0.0.0.0` | IPv4 bind address; use `127.0.0.1` for local-only sending. |
| `notify_port` | `8765` | Receiver TCP port. |
| `notify_autostart` | `true` | Set `false` to remove the login entry; an existing listener continues until stopped. |
| `notify_start_now` | `true` | With autostart enabled, also start a background listener if the desktop session environment is available. Set `false` to wait for the next graphical login. |
| `notify_auth` | `false` | Set `true` to generate/distribute a shared key and require authenticated messages. |
| `notify_key_file` | Controller's config directory + `/notify/key` | Absolute shared key path on the controller; set once for the whole deployment. |
| `notify_config_home` | Desktop user's home + `/.config` | Receiver's configuration directory. Set this to the user's actual `XDG_CONFIG_HOME` if customized. |

For example:

```sh
ansible-playbook deploy_notify.yml --limit ubuntu1 \
  -e notify_user=alice -e notify_port=9000

ansible-playbook deploy_notify.yml --limit ubuntu1 -e notify_autostart=false
```

For different desktop usernames, set `notify_user` per host in inventory or
`host_vars`. There is one configured receiver account per host; simultaneous
desktops on the same host would need separate ports and additional configuration.

## Preview changes

Syntax checking does not deploy anything:

```sh
ansible-playbook deploy_notify.yml --syntax-check
```

Key-free deployments can use `--check --diff` immediately. If using
`notify_auth=true`, before the first `--check` run create the controller key explicitly. If it
already exists, skip `keygen` (it intentionally refuses to overwrite keys):

```sh
python3 ../Notify/notify keygen
ansible-playbook deploy_notify.yml --limit ubuntu1 -e notify_auth=true --check --diff
```

Authenticated check mode requires an existing key so it does not create a secret during a
preview. For a custom `notify_key_file`, pass the same path to `keygen --key-file`.
Ansible's [check and diff modes](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_checkmode.html)
preview managed changes; key-copy tasks suppress secret diffs.
