# notify

Small pop-up messages between machines, with optional authentication. Copy the `notify` file to
each machine: it is a single Python program with no pip dependencies. Receivers
show native Linux desktop notifications; the sender also works on Windows/macOS
using `python notify ...`.

## Install on each Linux machine

To deploy to multiple machines with Ansible, use
[`Playbook/deploy_notify.yml`](../Playbook/deploy_notify.yml); see the
[deployment instructions](../Playbook/NOTIFY.md).
The playbook installs a standalone **receive-only** copy on targets, supporting
only `listen` and `autostart`. Send messages using this full program on the
controller; deployed targets have no `send`, `all`, or `keygen` commands.

For a manual receive-only installation, build that executable on the controller:

```sh
python3 build_receiver.py > notify-receiver
```

Copy `notify-receiver` to the target and install it as `notify` instead of the
full program below. The build reuses the receiver code without including the
sender. It limits the installed commands; restrict inbound access on receivers
to the controller if only that machine should be allowed to send notifications.

Requires Python 3.8+ and `notify-send` on receivers. For Debian/Ubuntu:

```sh
sudo apt install python3 libnotify-bin
```

On Fedora use `sudo dnf install python3 libnotify`; on Arch use
`sudo pacman -S python libnotify`.

From this folder, install as your regular desktop user:

```sh
mkdir -p "$HOME/.local/bin"
install -m 755 notify "$HOME/.local/bin/notify"
export PATH="$HOME/.local/bin:$PATH"
```

Ensure `~/.local/bin` is on your PATH in future terminals too, or use the full
`~/.local/bin/notify` path. You can also run `python3 ./notify` without installing.

## Start receiving

Open a terminal **inside the receiving user's Linux desktop** and run:

```sh
notify listen
```

Leave this running. It listens on TCP port **8765** on all IPv4 interfaces.
No keys or key generation are required.
Use `--host 192.168.1.20` to bind one interface or `--port 9000` to change the port.
If the receiver has a firewall, allow that port from your sender's IP.

The receiver needs a graphical session with a notification service, such as
GNOME, KDE Plasma, or a window manager running a notification daemon. Start it as
the logged-in desktop user, without `sudo`. A headless server or a plain SSH
session does not provide a desktop to show the pop-ups on.

## Send messages

From the sender (replace the example IP with the receiver's IP or hostname):

```sh
notify send 192.168.1.20 "Hello from the other machine!"
notify send 192.168.1.20 "Meeting in five minutes" --title "Reminder"
notify send 192.168.1.20 "Please save your work" --also 192.168.1.21 --also 192.168.1.22
notify send 192.168.1.20:9000 "Maintenance starts soon" --duration 15 --urgency critical
```

`--duration` is 1-300 seconds (default 8); urgency is `low`, `normal`, or
`critical`. Titles are limited to 200 characters and messages to 4,000 characters.
Text is displayed literally, including shell characters and HTML tags.

## Notify all targets in ranges or lists

```sh
notify all '10.42.1-13.10' "Please save your work"
notify all '10.42.1.(10,20,30,40)' "Meeting in five minutes"
notify all '10.42.1-13.(10,20,30,40)' "Maintenance starts soon" --title Reminder
notify all '10.42.1-3.10-20:9000' "Hello" --also '10.42.5.(10,30):9000'
```

Ranges are inclusive. Lists use parentheses and commas; list entries can also
be ranges, e.g. `(10,20-25,40)`. Both the third and fourth octets support this
syntax; the first two must be fixed numbers. When both octets contain ranges or
lists, every combination is targeted: `10.42.1-13.(10,20,30,40)` targets **52**
addresses. Octets must be 0-255 and ranges must be ascending. Quote patterns,
especially those containing parentheses, to prevent the shell interpreting them.

`all` sends to the supplied addresses with up to **16** concurrent deliveries.
It does not discover machines automatically. `send` also accepts patterns and
defaults to one delivery at a time. Both accept `--workers 1-64`, `--also`, and
the same title, urgency, duration, and optional key settings. Overlapping targets
are deduplicated, and all patterns are validated before any messages are sent.

Each target reports success or failure. A failed or offline target is skipped
and delivery continues to every other target; messages are not queued. At the
end, both commands print a summary, for example:

```text
Finished: 48/52 targets accepted the notification; 4 failed.
```

Exit status is 0 if all targets accepted the message, 1 if any failed.
Success means the desktop notification service accepted
the message, not that a person read it. Do Not Disturb, lock-screen settings, and
desktop notification preferences may suppress the pop-up. Some desktops ignore
requested durations, including GNOME Shell; see the
[notify-send manual](https://manpages.debian.org/unstable/libnotify-bin/notify-send.1.en.html).

## Optional: start at desktop login

After installing the program, run as the receiving user:

```sh
notify autostart
```

This writes `~/.config/autostart/notify.desktop`, following the
[desktop autostart standard](https://specifications.freedesktop.org/autostart/latest/).
It starts the receiver at the next graphical login. Run `notify listen` to start
it now; stop a manually started receiver with Ctrl+C before starting another.
The login entry uses the current program's absolute path, so keep the installed
file there. Custom `--host`, `--port`, and `--key-file` settings also work here.

To disable login startup:

```sh
notify autostart --disable
```

This removes the login entry; a running receiver stops when you log out. To
uninstall, disable autostart, stop the receiver, and remove `~/.local/bin/notify`.
Delete the shared key on that machine if it is no longer needed.

## Network and authentication

Use this on a trusted LAN or through a VPN. The included listener serves HTTP;
message contents are not encrypted. By default, no key is required, so any
machine able to reach the listener can send a notification.

To opt into authentication, generate a key once on the sender:

```sh
notify keygen
```

This creates `~/.config/notify/key` with private file permissions and refuses to
overwrite an existing file. If `XDG_CONFIG_HOME` is set, the default location is
`$XDG_CONFIG_HOME/notify/key`. Copy this same key securely to each receiver,
then explicitly pass `--key-file` on both ends:

```sh
notify listen --key-file ~/.config/notify/key
notify all '10.42.1-13.10' "Hello" --key-file ~/.config/notify/key
notify autostart --key-file ~/.config/notify/key
```

Existing key files are ignored unless `--key-file` is supplied. Previously
installed autostart entries that include `--key-file` keep requiring a key;
run `notify autostart` again and restart the listener to switch to key-free mode.

With authentication enabled, each request has an HMAC-SHA256 signature,
a timestamp, and a random nonce: the key is never transmitted, and modified,
unsigned, and replayed requests are rejected. Keep sender and receiver clocks
within 60 seconds. Replay protection is held in memory and resets on restart.
Anyone holding the shared key can send messages; there is no separate sender
identity or per-user permission model.

Do not expose this small HTTP listener directly to the public internet. For
remote networks, use a VPN. HTTPS URLs are also accepted by the sender if you
provide a TLS reverse proxy with a trusted certificate in front of the receiver;
specify its port explicitly, e.g. `https://desktop.example:443`.

## Troubleshooting and tests

- **No pop-up:** run `notify-send "Test" "Desktop notifications work"` in the
  receiver's desktop terminal. Check notification settings and Do Not Disturb.
- **Connection refused/timed out:** check the receiver is running, its IP/port,
  network routing, and the receiver's firewall.
- **Authentication failed:** both ends must use the same key and synchronized
  clocks. Every receiver starts with an empty replay cache.
- **Address already in use:** another receiver may already be running; stop it
  or choose another port.

Run the automated tests from this folder:

```sh
python3 -m unittest discover -s tests -v
```

Tests use real loopback HTTP connections with a substituted popup backend, so
they also run on machines without a graphical Linux desktop.
