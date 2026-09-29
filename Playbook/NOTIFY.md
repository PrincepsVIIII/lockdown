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
ansible-playbook deploy_notify.yml --limit ubuntu1
```

This installs `/usr/local/bin/notify` and its dependencies, distributes a shared
key with mode `0600`, and configures startup at graphical login. The default
desktop user is the inventory's `ansible_user` (`sysadmin` in this inventory).
If another account logs into the desktop, specify it:

```sh
ansible-playbook deploy_notify.yml --limit 10.1.1.10 -e notify_user=alice
```

Use `--limit 'ubuntu1:ubuntu2'` for both desktop groups. Omit `--limit` to target
the entire `linux` group, including its server groups. Only hosts with a graphical
desktop and notification service can display pop-ups. Add `-K` if sudo requires
a password that is not already configured in the inventory.

The playbook prepares login startup. **The receiver starts at the next graphical
login**, not immediately from the SSH deployment session. To start immediately,
run `notify listen` in the target user's desktop terminal. The playbook prints
the full command if you selected a custom key path, host, or port. If updating an
already running receiver, restart it or log out/in to load the new program,
settings, or key. Do not run two listeners on the same address and port.

## Shared key and sending

The first run generates a key on the controller at `~/.config/notify/key`
(`$XDG_CONFIG_HOME/notify/key` if set). Later runs reuse it. All targeted
receivers receive that same key in the selected desktop user's configuration
directory. Existing receiver keys are replaced with the controller's key.
Keep the controller key to continue sending messages and deploying more hosts.
Key contents are hidden from Ansible output and diffs.

From the `Playbook` directory on that controller:

```sh
python3 ../Notify/notify send 10.1.1.10 "Hello from Ansible's controller!"
python3 ../Notify/notify send 10.1.1.10 "Meeting soon" --also 10.2.1.10 --title Reminder
```

Senders on other machines need a copy of `notify` and the same shared key.
Allow inbound TCP **8765** from the sender's address in the receiving machine's
firewall. The playbook does not change firewall rules. Use a trusted LAN or VPN;
the listener authenticates messages but does not encrypt their contents.

## Settings

Set these with `-e`, `host_vars`, or `group_vars` as appropriate:

| Variable | Default | Purpose |
| --- | --- | --- |
| `notify_user` | `ansible_user` | Existing account whose desktop receives pop-ups. |
| `notify_host` | `0.0.0.0` | IPv4 bind address; use `127.0.0.1` for local-only sending. |
| `notify_port` | `8765` | Receiver TCP port. |
| `notify_autostart` | `true` | Set `false` to remove the login entry; an existing listener continues until stopped. |
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

Before the first `--check` run, create the controller key explicitly. If it
already exists, skip `keygen` (it intentionally refuses to overwrite keys):

```sh
python3 ../Notify/notify keygen
ansible-playbook deploy_notify.yml --limit ubuntu1 --check --diff
```

Check mode requires an existing key so it does not create a secret during a
preview. For a custom `notify_key_file`, pass the same path to `keygen --key-file`.
Ansible's [check and diff modes](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_checkmode.html)
preview managed changes; key-copy tasks suppress secret diffs.
