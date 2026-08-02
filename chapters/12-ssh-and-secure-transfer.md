---
part: IV
part_title: Networking & Remote Access
number: 12
title: SSH & Secure Transfer
tagline: How to remotely manage a server securely, why telnet and FTP are dangerous, and which tools move files across networks without exposing passwords.
source: PDF p95-97 + p280-295 quiz bank
minutes: 60
---

## 1 · The Big Picture

Everything you do on a server, someone did over the network. Decades ago, that "someone" used **telnet** to log in, **rsh** to run commands, **rlogin** for passwordless login, and **FTP** to move files. All of them transmitted usernames and passwords in cleartext — visible to anyone watching the network. By the 1980s that was obviously broken.

In 1995, Tatu Ylönen, frustrated by a password-sniffing attack on his university network, wrote **SSH** — the **Secure Shell**. It replaced telnet/rsh/rlogin with encrypted sessions where even an attacker reading every byte of traffic sees only random data. It replaced FTP with SCP and SFTP. Today, SSH is the only sane way to remotely administer a Unix system; it is effectively universal on Linux and macOS, and increasingly standard on Windows.

This chapter teaches you:

- **Why cleartext protocols die** — telnet, FTP and rsh compared
- **How SSH works** — the connection sequence, key exchange, authentication
- **Generating and managing keys** — why Ed25519 matters, file permissions, `ssh-agent`
- **The `ssh` client in depth** — all the options, config files, port forwarding
- **Server hardening** — `sshd` configuration, lockout procedures, security audit
- **File transfer** — `scp`, `sftp`, and `rsync` with delta-transfer intuition
- **Production patterns** — deploy keys, authorized\_keys restrictions, automation

### Where you will encounter it

| Context | What SSH is doing there |
|---|---|
| Every cloud VM you SSH into | The encrypted tunnel from your laptop to EC2, Compute Engine, or Droplet |
| Container exec (`docker exec`) | Inherits process namespace; but pull/push images over HTTPS |
| Git over SSH | `git@github.com:...` — pushing code without a password in memory |
| CI/CD deploy steps | Build systems SSH to servers to deploy, using deploy keys without passphrases |
| Bastion / jump hosts | Multi-hop routing through an internal gateway to reach locked-down infrastructure |
| SCP / rsync migrations | Moving terabytes of database files, backups, or entire filesystems between machines |
| Tunnelling databases | `ssh -L 3306:localhost:3306` to reach a MySQL that has no public IP |

---

## 2 · Intuition First

### Why telnet and FTP lost

Telnet is a bare TCP connection. You type `telnet example.com 23` and your keystrokes go straight into the network unencrypted. An attacker on the same network (or with access to your ISP's routing) reads:

```
login: admin
Password: MySecureP@ss
```

FTP is the same — username and password in the clear. The attacker now has root.

SSH changed the model: before any credentials are sent, both sides prove they have shared secrets *without revealing those secrets*. The server proves its identity, the client proves theirs, and then they encrypt everything. All of this is auditable and automatic.

### The three phases of an SSH connection

```diagram title="Three phases of SSH"
Phase 1: TRANSPORT LAYER      Phase 2: KEY EXCHANGE             Phase 3: AUTHENTICATION
├─ TCP connect                ├─ Both sides send version        ├─ Public-key or password
├─ Negotiate protocol          ├─ Negotiate algorithms          ├─ After auth succeeds,
│  version (SSH-2.0)           ├─ Diffie-Hellman or ECDH        │  open a channel
├─ Establish TCP tunnel        ├─ Derive shared session key      ├─ Shell or command
└─ Ready for key exchange      ├─ Verify host key               └─ Encrypted messages
                               └─ *still no auth yet*

       ↓ after all 3: authenticated encrypted channel ↓
```

### Public-key cryptography intuition: paint mixing

Imagine you and a friend each have a secret colour — say, you have blue and they have red. You both also have a public colour — say, yellow.

1. You mix your secret blue + public yellow → a unique shade you send to them.
2. They mix their secret red + public yellow → a unique shade they send you.
3. Now both of you mix the shade you received + your own secret colour.
4. **Mathematically, you both arrive at the same final colour**, even though you never shared either secret.

SSH uses the same idea with math (Diffie-Hellman or elliptic curves) instead of paint. Two strangers derive a shared secret while an eavesdropper watches every exchange and learns nothing.

### Symmetric vs asymmetric: why you need both

**Asymmetric encryption** (RSA, Ed25519) is *slow*. Encrypting a gigabyte with an RSA key takes minutes. **Symmetric encryption** (AES) is *fast* — gigabytes per second.

So SSH does this:

- **Use asymmetric (public-key) to prove identity and securely agree on a session key.** The server proves it is who it claims; the client proves it is authorized.
- **Use symmetric (AES-128-GCM, ChaCha20) to encrypt all the subsequent traffic.** Fast, proven, standard.

**Your private key never leaves your machine and is never sent to the server.** It only ever signs messages, proving you have it without revealing it.

---

## 3 · Technical Definitions

**SSH (Secure Shell).** A protocol (RFC 4251–4254) providing confidentiality, integrity and authentication over an insecure network. It comprises three layers:

| Layer | Purpose | Mechanism |
|---|---|---|
| Transport | Encrypt the stream | TCP + chosen cipher (AES-GCM, ChaCha20) + MAC |
| Authentication | Prove identity | Public-key, password, or other methods |
| Connection | Open channels | Shell, command, port forward, SFTP subsystem |

**Confidentiality** means an eavesdropper cannot read the plaintext. **Integrity** means a modified packet is detected and discarded. **Authentication** means you know you are talking to the claimed server and the server knows you are authorized.

**Asymmetric (public-key) cryptography.** A key pair where one key (private) is kept secret and the other (public) is shared. Anything encrypted with the public key can only be decrypted with the private key. In SSH, this is used for:

- **Host authentication** — the server proves its identity by signing a challenge.
- **Client authentication** — the client signs a challenge with its private key.

**Symmetric (session) key cryptography.** A single secret key shared between both sides. Fast; used for bulk encryption of the session after key exchange.

**Key exchange (Kex).** The process of both sides negotiating a shared session key without either sending the key itself. SSH supports Diffie-Hellman (over integers or elliptic curves) and now prefers the elliptic-curve variants.

**Host key.** The asymmetric key pair that identifies a specific server. Stored in `/etc/ssh/ssh_host_*_key` on the server. The public half is checked against `~/.ssh/known_hosts` on the client to prevent man-in-the-middle (MITM) attacks.

---

## 4 · Internal Working

### The SSH connection sequence

```mermaid
sequenceDiagram
    autonumber
    participant C as Client<br/>(your laptop)
    participant K as Kernel
    participant S as SSH server<br/>(remote host)
    C->>K: TCP connect to 192.168.1.50:22
    K->>S: establish TCP connection
    S-->>K: TCP established
    K-->>C: TCP established
    C->>S: "SSH-2.0-OpenSSH_9.3"
    S-->>C: "SSH-2.0-OpenSSH_9.3"
    Note over C,S: Version exchange (negotiate protocol version)
    C->>S: key_init: propose ciphers, MACs, kex algorithms
    S-->>C: key_init: agree on algorithms
    Note over C,S: Key exchange (Diffie-Hellman or ECDH)
    C->>S: [kex_ecdh_init with ephemeral public key]
    S-->>C: [kex_ecdh_reply: server's ephemeral key + host key + signature]
    Note over C,S: Both sides derive same session key; client verifies host key
    C->>C: Check server's host key against ~/.ssh/known_hosts
    alt Host key unknown or changed
        C->>C: Prompt user: "Host key not in known_hosts. Accept? (yes/no/fingerprint)"
        C->>S: DISCONNECT if user says no
    end
    Note over C,S: Transport layer now encrypted with session key
    C->>S: [SSH_MSG_SERVICE_REQUEST ssh-userauth]
    S-->>C: [SSH_MSG_SERVICE_ACCEPT]
    Note over C,S: User authentication
    C->>S: [SSH_MSG_USERAUTH_REQUEST: user=alice, method=publickey, pubkey_blob]
    S-->>C: Check if user alice has this public key in authorized_keys
    alt Public key matches
        S-->>C: [SSH_MSG_USERAUTH_SUCCESS]
        Note over C,S: Channel open; shell or command ready
        C->>S: [SSH_MSG_CHANNEL_OPEN session]
        S-->>C: [SSH_MSG_CHANNEL_OPEN_CONFIRMATION]
        C->>S: [SSH_MSG_CHANNEL_REQUEST shell or exec]
        S-->>C: PTY allocated / command executes
        S-->>C: Output streaming over encrypted channel
    else Public key not found or auth fails
        S-->>C: [SSH_MSG_USERAUTH_FAILURE]
        Note over C: Connection closed or retry with different key
    end
```

### Reading the host key check

When you SSH to a server for the first time, you see:

```console
$ ssh example.com
The authenticity of host 'example.com (93.184.216.34)' can't be established.
ED25519 key fingerprint is SHA256:8AV2FQ42SkZgqPDjd4...
This key is not known by any system.
Are you sure you want to continue connecting (yes/no/[fingerprint])?
```

What is actually happening:

1. The server sent its public key (an Ed25519 key in this case).
2. SSH computed its SHA256 fingerprint: `8AV2FQ42SkZgqPDjd4...`
3. SSH checked `/home/youruser/.ssh/known_hosts` and found no entry for `example.com`.
4. SSH is asking: do you trust this key?

If you type `yes`, SSH appends the entry to `known_hosts`:

```console
example.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEv...
```

Next time you connect, SSH verifies the key matches. If it does not — e.g., someone redirected `example.com` to a different server — SSH aborts with:

```console
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@    WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!     @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!
Someone could be eavesdropping on you right now (man-in-the-middle attack)!
```

This is your only defence against MITM attacks. The server is also authenticating you (via keys), so credential theft is not possible.

### Private key cryptography

Your private key is the credential. It is typically stored at `~/.ssh/id_ed25519` and looks like:

```
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUtbm9uZS1ub25lAAAAAAAAAEsAAAAHc3NoLXJzYQAA
AAAB3NzaC1lZDI1NTE5AAAAIOhEv2B9A7...
-----END OPENSSH PRIVATE KEY-----
```

It is encrypted with a passphrase you choose (or empty if you skip it). When you use the key:

1. `ssh` reads the file and decrypts it using your passphrase.
2. `ssh` signs a challenge issued by the server: `sign(challenge, private_key)`.
3. The server checks the signature using your public key: `verify(signature, challenge, public_key)`.
4. If it matches, you are authenticated. **The private key was never sent.**

> [!TIP]
> Using a strong passphrase protects your key if someone reads your disk (stolen laptop, forensic analysis of a decommissioned instance). But passphrases are tedious to type constantly. That is why `ssh-agent` exists: it caches decrypted keys in memory.

### The permission model: SSH will refuse loose permissions

SSH has a philosophy: **if the permissions are wrong, the key does not work, period.** This prevents accidentally making your private key world-readable or making `authorized_keys` modifiable by untrusted users.

| File / Directory | Required permission | Why |
|---|---|---|
| `~/.ssh` | 700 (drwx------) | Only you can read, write, execute (enter) |
| `~/.ssh/id_ed25519` | 600 (-rw-------) | Only you can read the private key |
| `~/.ssh/id_ed25519.pub` | 644 (-rw-r--r--) | World-readable public key, only you write |
| `~/.ssh/authorized_keys` | 600 (-rw-------) | Only you should modify who can log in |
| `~/.ssh/known_hosts` | 600 (-rw-------) | Sensitive: fingerprints of servers you trust |
| `~/.ssh/config` | 600 (-rw-------) | May contain credentials or private hostnames |

If permissions are wrong, you get errors:

```console
$ ssh example.com
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@         WARNING: UNPROTECTED PRIVATE KEY FILE!          @
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
Permissions 0644 for '/home/alice/.ssh/id_ed25519' are too open.
It is recommended that your private key files are not accessible by others.
This private key will be ignored.
```

Fix it with `chmod 600 ~/.ssh/id_ed25519`. SSH will not use a key it considers unsafe.

---

## 5 · Real Examples

### Example 1: First-time login to a fresh server

You launch a cloud VM. The cloud provider gives you an IP address and a private key (usually a `.pem` file).

```bash
# You have the key locally
ls -la ~/Downloads/mykey.pem
# Fix permissions (the file is usually world-readable after download)
chmod 600 ~/Downloads/mykey.pem

# SSH in, specifying the key
ssh -i ~/Downloads/mykey.pem ubuntu@203.0.113.42
```

You will see the host key prompt. Accept it (unless you have reason to suspect MITM).

```console
The authenticity of host '203.0.113.42 (203.0.113.42)' can't be established.
ED25519 key fingerprint is SHA256:AbCdEf...
Are you sure you want to continue connecting (yes/no/[fingerprint])? yes
```

Now you are logged in.

### Example 2: Setting up passwordless login

You have a development server where you will work frequently. You want to avoid typing a password (or a passphrase) every time.

**On your local machine:**

```bash
# Generate a new key pair for this server (optional, or reuse ~/.ssh/id_ed25519)
ssh-keygen -t ed25519 -C "alice@laptop-2024"
# Generates ~/.ssh/id_ed25519 and ~/.ssh/id_ed25519.pub
# Leave passphrase empty to avoid typing it on each `ssh`
```

**Deploy the public key to the server:**

```bash
# Option A: use ssh-copy-id (recommended)
ssh-copy-id -i ~/.ssh/id_ed25519.pub alice@192.168.1.50

# Option B: do it manually (if ssh-copy-id is not available)
cat ~/.ssh/id_ed25519.pub | ssh alice@192.168.1.50 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

**Test:**

```bash
ssh alice@192.168.1.50
# No password prompt; you are logged in immediately
```

### Example 3: Running a command on a remote server

```bash
ssh alice@192.168.1.50 "ps aux | grep nginx | wc -l"
# Output appears locally; connection closes after command finishes
```

Important: quote the command to prevent local shell expansion:

```bash
# WRONG: $HOSTNAME is expanded locally
ssh user@remote echo $HOSTNAME
# Output: your local hostname, not the remote one

# CORRECT: $HOSTNAME is expanded on the remote server
ssh user@remote 'echo $HOSTNAME'
# Output: the remote hostname
```

### Example 4: Copy a file using SCP

```bash
# Copy local file to remote
scp -P 22 /path/to/file.txt alice@192.168.1.50:/tmp/
# Note: -P (capital) for port on scp, not -p

# Copy remote file to local
scp -P 22 alice@192.168.1.50:/var/log/syslog ~/Downloads/

# Copy a directory recursively
scp -r -P 22 alice@192.168.1.50:/home/alice/project ~/
```

### Example 5: Production setup — deploy key with restricted permissions

You have a CI/CD system that auto-deploys. You want to let it SSH to production servers, but only to run the deploy script, not to open a shell.

**Generate a deploy key (no passphrase):**

```bash
ssh-keygen -t ed25519 -f ~/.ssh/deploy_key -N ""
# ~/.ssh/deploy_key and ~/.ssh/deploy_key.pub
```

**On the production server, add to `authorized_keys` with restrictions:**

```bash
echo 'command="/opt/deploy.sh",no-port-forwarding,no-agent-forwarding,no-X11-forwarding ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... gitlab-ci@build-001' >> ~/.ssh/authorized_keys
```

Now the CI system can SSH and run the deploy, but:

- Even if it SSH's, it *only* runs `/opt/deploy.sh`; it cannot open a shell
- It cannot create port forwards or forward the agent
- It cannot open X11 connections

This is called "deploying with restricted keys" and is a core DevOps security practice.

### Example 6: Tunnelling a database connection

Your PostgreSQL server has no public IP. You can SSH to the web server that can reach it internally. You want to connect from your laptop to Postgres as if it were local.

```bash
ssh -L 5432:localhost:5432 ubuntu@web.example.com
# Now, on your laptop:
psql postgres://localhost:5432/mydb
# Connection is tunnelled through SSH to the web server, then locally to Postgres
```

The `-L` flag syntax is `-L [local_addr:]local_port:remote_host:remote_port`.

### Example 7: Using rsync for a backup

```bash
# Backup /var/www from a server to local
rsync -avz --delete alice@backup.example.com:/var/www/ ~/backups/www/

# Flags:
# -a (archive): recursive, preserve permissions, timestamps, symlinks
# -v (verbose): list files as they are transferred
# -z (compress): compress on the wire
# --delete: remove files locally that do not exist remotely
# (trailing slash matters: see Cheat Sheet)
```

---

## 6 · Practical Demonstration

### Generating keys with `ssh-keygen`

The command to remember: `ssh-keygen -t <type> -C <comment>`

```bash
# Best practice: Ed25519 (modern, small, fast, secure)
ssh-keygen -t ed25519 -C "alice@laptop-2024"
```

You will be prompted:

```console
Generating public/private ed25519 key pair.
Enter file in which to save the key (/home/alice/.ssh/id_ed25519):
Enter passphrase (empty for no passphrase):
Enter same passphrase again:
Your identification has been saved in /home/alice/.ssh/id_ed25519
Your public key has been saved in /home/alice/.ssh/id_ed25519.pub
The key fingerprint is:
SHA256:aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890abcd alice@laptop-2024
```

Every option to `ssh-keygen`:

| Option | Long form | Purpose | Example |
|---|---|---|---|
| `-t` | `--type` | Key type: `ed25519`, `rsa`, `ecdsa`, `dsa` | `ssh-keygen -t ed25519` |
| `-b` | `--bits` | Key size (RSA/ECDSA only) | `ssh-keygen -t rsa -b 4096` |
| `-f` | `--file` | Output file path | `ssh-keygen -f ~/.ssh/deploy_key` |
| `-N` | `--new-passphrase` | Passphrase (empty string = no passphrase) | `ssh-keygen -N ""` |
| `-p` | `--change-passphrase` | Change passphrase on existing key | `ssh-keygen -p -f ~/.ssh/id_ed25519` |
| `-y` | `--show-key` | Extract public key from private key | `ssh-keygen -y -f ~/.ssh/id_ed25519` |
| `-l` | `--fingerprint` | Print key fingerprint | `ssh-keygen -l -f ~/.ssh/id_ed25519` |
| `-R` | `--remove-host` | Remove host from `known_hosts` | `ssh-keygen -R example.com` |
| `-o` | `--format` | Use modern format (OpenSSH instead of PEM) | `ssh-keygen -o -t rsa` |
| `-a` | `--rounds` | KDF rounds for key encryption (higher = slower but more resistant to brute force) | `ssh-keygen -a 100 -t ed25519` |

**Key type comparison:**

| Type | Size | Speed | Security | Modern | When to use |
|---|---|---|---|---|---|
| **Ed25519** | 256 bits | Very fast | Very high | Yes | Default choice, all new systems |
| ECDSA (P-256) | 256 bits | Fast | High | Yes | Cloud defaults if no Ed25519 |
| RSA 4096 | 4096 bits | Slower | High | ⚠ | Legacy systems, widely supported |
| RSA 2048 | 2048 bits | Slower | Medium | ✘ | Deprecated; do not use for new keys |
| DSA | 1024 bits | Slow | Low | ✘ | Obsolete; SSH servers reject it |

### The `ssh` client — every important flag

```bash
ssh [options] [user@]hostname [command]
```

| Short | Long | Purpose | Example |
|---|---|---|---|
| `-p` | `--port` | Remote port (default 22) | `ssh -p 2222 example.com` |
| `-i` | `--identity` | Private key to use | `ssh -i ~/.ssh/deploy_key user@example.com` |
| `-l` | `--login-name` | Username (alternative to `user@hostname`) | `ssh -l alice example.com` |
| `-v` | `--verbose` | Debug output (repeat for more: `-vv`, `-vvv`) | `ssh -vvv example.com` |
| `-o` | `--option` | Set config option on the command line | `ssh -o StrictHostKeyChecking=no ...` |
| `-t` | `--tty` | Force PTY allocation (for interactive shells) | `ssh -t host 'less file'` |
| `-T` | | Disable PTY allocation | `ssh -T git@github.com` |
| `-N` | `--no-command` | Do not execute remote command (use for port forward) | `ssh -N -L 5432:localhost:5432 host` |
| `-f` | `--background` | Go to background after authentication | `ssh -f -N -L 5432:localhost:5432 host` |
| `-q` | `--quiet` | Suppress all warnings and diagnostic messages | `ssh -q example.com` |
| `-C` | `--compress` | Enable compression (rarely useful with modern SSH ciphers) | `ssh -C example.com` |
| `-X` | | Enable X11 forwarding (untrusted) | `ssh -X user@desktop-linux` |
| `-Y` | | Enable X11 forwarding (trusted) | `ssh -Y user@desktop-linux` |
| `-A` | | Enable agent forwarding | `ssh -A bastion.example.com` |
| `-L` | | Local port forward | `ssh -L 5432:localhost:5432 host` |
| `-R` | | Remote port forward | `ssh -R 8080:localhost:8080 host` |
| `-D` | | Dynamic SOCKS proxy | `ssh -D 1080 bastion.example.com` |
| `-J` | | ProxyJump (SSH through a bastion) | `ssh -J bastion.example.com prod.internal` |
| `-F` | | Use a specific config file | `ssh -F ~/.ssh/config.custom host` |

### SSH config file: the high-leverage tool

`~/.ssh/config` lets you define host-specific settings so you never repeat them:

```ini
# Default for all hosts
Host *
    ServerAliveInterval 60
    Compression yes
    ControlMaster auto
    ControlPath ~/.ssh/control-%h-%p-%r
    ControlPersist 600

# Production server
Host prod
    HostName prod.example.com
    User ubuntu
    Port 2222
    IdentityFile ~/.ssh/prod_key
    IdentitiesOnly yes
    StrictHostKeyChecking accept-new
    UserKnownHostsFile ~/.ssh/prod_known_hosts

# Through a bastion
Host prod-internal
    HostName 10.0.1.50
    User ubuntu
    ProxyJump bastion.example.com

# Allow any hostname under *.internal via proxy
Host *.internal
    ProxyJump bastion.example.com
    User ubuntu

# Git over SSH
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_key
    IdentitiesOnly yes
```

Now you can:

```bash
ssh prod                                  # Uses prod settings
ssh user@prod.example.com:2222 -p 2222    # Still works, but repetitive
ssh prod-internal                         # Goes through bastion automatically
ssh some-app.internal                     # ProxyJump applies via pattern
```

Important config options:

| Option | Value | Meaning |
|---|---|---|
| `Host` | pattern | This block applies to hostnames matching pattern |
| `HostName` | IP or hostname | Actual host to connect to |
| `User` | username | Remote username |
| `Port` | number | Remote port |
| `IdentityFile` | path | Private key to try |
| `IdentitiesOnly` | yes/no | Only use keys in `IdentityFile`; do not try agent or default keys |
| `ProxyJump` | hostname | SSH through this host first |
| `ForwardAgent` | yes/no | Allow remote host to use your agent (`-A` flag) |
| `ServerAliveInterval` | seconds | Keep-alive: send null packet every N seconds |
| `ControlMaster` | auto/yes/no/ask | Session multiplexing: reuse connections |
| `ControlPath` | path | Where to put the control socket for multiplexing |
| `ControlPersist` | yes/no/seconds | Keep control socket open after disconnecting |
| `StrictHostKeyChecking` | yes/accept-new/no | Behavior when host key changes: yes=fail, accept-new=add but do not change, no=no checking |
| `AddKeysToAgent` | yes/no/ask/confirm | Automatically add keys to agent on auth success |
| `Compression` | yes/no | Compress traffic (usually no, as ciphers are already fast) |
| `ChrootDirectory` | path | (Server only) Chroot after auth |

> [!TIP]
> **A good `~/.ssh/config` is one of the highest-leverage investments.** It eliminates typing usernames, ports, key paths, and bastion hops. Version control it (without private keys), and you will never have to reconfigure on a new machine.

### SSH agent: caching decrypted keys

A passphrase-protected key is great for security, but entering it for every command is tedious. The SSH agent caches decrypted keys in memory.

```bash
# Start the agent (usually automatic in modern shells)
eval "$(ssh-agent -s)"
# or, in fish:
eval (ssh-agent -c)

# Add your key to the agent (you will be prompted for the passphrase once)
ssh-add ~/.ssh/id_ed25519
# ssh-add: Identity added: /home/alice/.ssh/id_ed25519 (alice@laptop-2024)

# List keys currently in the agent
ssh-add -l
# 256 SHA256:aBcD... alice@laptop-2024 (ED25519)

# Remove a key from the agent
ssh-add -d ~/.ssh/id_ed25519

# Remove all keys
ssh-add -D
```

Now, `ssh` will use the cached key without prompting. If your computer restarts, the agent is emptied; you will need to run `ssh-add` again.

> [!WARNING]
> **Agent forwarding (`-A`) must be used carefully.** When you use `ssh -A bastion.example.com` and then SSH from the bastion to another host, the bastion can read your SSH agent socket and impersonate you on any host your agent has keys for. **Only use agent forwarding with hosts you completely trust.** For multi-hop scenarios, use `ProxyJump` instead, which does not expose your agent.

### Port forwarding: three patterns

#### Pattern 1: Local forward (`-L`)

You want to reach a service that is not publicly accessible. It is reachable from a machine you can SSH to.

```bash
ssh -L local_port:internal_host:internal_port user@ssh_host
# -L [bind_addr:]local_port:remote_host:remote_port

# Example: access internal PostgreSQL through a jump host
ssh -L 5432:db.internal:5432 ubuntu@bastion.example.com
# Now, on your local machine:
# psql postgresql://localhost:5432/mydb
# The connection is tunnelled: local → SSH tunnel → bastion → db.internal:5432
```

Keep the SSH session open. To background it:

```bash
ssh -f -N -L 5432:localhost:5432 ubuntu@bastion.example.com
# -f = background after auth
# -N = do not execute a command
```

#### Pattern 2: Remote forward (`-R`)

You want to expose a service on your local machine to a remote server that cannot reach you directly. You have outbound SSH access to that server.

```bash
ssh -R remote_port:localhost:local_port user@remote_host

# Example: expose your local dev server to production bastion for testing
ssh -R 8080:localhost:8080 ubuntu@bastion.example.com
# Now, on bastion.example.com:
# curl http://localhost:8080/
# Connection is tunnelled: bastion → SSH tunnel → your local machine:8080
```

By default, the remote port is only accessible from the remote machine itself (`localhost`). To make it accessible to other machines on the remote network, set `GatewayPorts yes` in `/etc/ssh/sshd_config` on the remote host.

#### Pattern 3: Dynamic forward (SOCKS proxy) (`-D`)

You want all your traffic from a local application to exit through a remote server. The remote server becomes a SOCKS5 proxy.

```bash
ssh -D 1080 ubuntu@bastion.example.com
# Now, configure your browser to use SOCKS proxy localhost:1080
# All traffic flows through bastion
```

This is useful for:

- Reaching internal services as if you were on the internal network
- Hiding your IP from certain destinations
- Proxying traffic without a VPN

### SCP: Secure Copy with SSH

```bash
scp [options] source destination
```

Syntax:

```bash
# Local to remote
scp /path/to/file user@host:/remote/path/

# Remote to local
scp user@host:/remote/file /path/to/local/

# Remote to remote
scp user1@host1:/path/file user2@host2:/path/

# Directory
scp -r /path/to/dir user@host:/remote/
```

Every important option:

| Option | Purpose | Example |
|---|---|---|
| `-P port` | SSH port (note: capital P, unlike ssh) | `scp -P 2222 file user@host:/` |
| `-r` | Recursive (directories) | `scp -r ~/project user@host:/` |
| `-C` | Compression | `scp -C largefile user@host:/` |
| `-p` | Preserve file modification times and permissions | `scp -p file user@host:/` |
| `-q` | Quiet; suppress progress meter | `scp -q file user@host:/` |
| `-i key` | Private key | `scp -i ~/.ssh/deploy_key file user@host:/` |
| `-3` | Copy via local machine (not direct remote-to-remote) | `scp -3 user1@host1:/a user2@host2:/b` |
| `-o option` | SSH option (e.g. `-o ConnectTimeout=10`) | `scp -o ConnectTimeout=10 file user@host:/` |

> [!WARNING]
> **OpenSSH 9+ changed SCP internally.** Older versions used the SCP protocol (a binary protocol over SSH); OpenSSH 9+ now uses SFTP by default internally, which is more efficient and more secure. The command syntax is the same, but the wire protocol changed. If you need the old SCP protocol, use `-O`.

Real example — backup a remote file with compression:

```bash
scp -C -p ubuntu@backup.example.com:/var/backups/db.sql.gz ~/backups/
```

### SFTP: interactive file transfer

SCP is one-shot. SFTP is interactive, like FTP but over SSH.

```bash
sftp user@host
# Connected to host.
sftp> ls
# List remote directory

sftp> cd /var/log
sftp> get syslog ~/Downloads/
# Download file

sftp> put ~/file.txt
# Upload file

sftp> quit
```

Or, use `sftp -b` to run a batch of commands:

```bash
cat > batch.txt << 'EOF'
cd /var/log
get syslog
quit
EOF

sftp -b batch.txt user@host
```

### Rsync: delta transfer at scale

`rsync` is the standard for moving large amounts of data efficiently. It uses **rolling checksums** to detect changes and only transfers differences, not whole files.

```bash
rsync [options] source destination

# Examples
rsync -avz user@host:/source/path/ ~/local/path/
rsync -avz ~/local/path/ user@host:/remote/path/
```

Every important option:

| Option | Long | Purpose |
|---|---|---|
| `-a` | `--archive` | Recursive, preserve permissions/ownership/timestamps/symlinks — usually what you want |
| `-v` | `--verbose` | List files as transferred |
| `-z` | `--compress` | Compress on the wire (slower CPU, less bandwidth) |
| `-h` | `--human-readable` | Show file sizes in human form |
| `-P` | `--partial --progress` | Show progress bar; keep partial files if interrupted |
| `-n` | `--dry-run` | Do not transfer; show what would happen |
| `--delete` | — | Remove files from destination that do not exist in source |
| `--delete-after` | — | Delete after transfer (safer; you can see what is deleted) |
| `--exclude PATTERN` | — | Skip files matching PATTERN |
| `--exclude-from FILE` | — | Exclude files listed in FILE |
| `--include PATTERN` | — | Include files (useful with `--exclude` for complex rules) |
| `-e 'ssh -p 2222'` | — | Use custom SSH (different port, key, etc.) |
| `--bwlimit KB` | — | Rate limit (KB per second) |
| `--checksum` | — | Use checksum instead of modification time and size |
| `--size-only` | — | Skip files if size matches (do not check time) |
| `--link-dest DIR` | — | Hard-link unchanged files from previous backup (snapshot backup) |
| `--numeric-ids` | — | Preserve UID/GID numerically (useful across different systems) |

**The trailing slash rule — critical:**

```bash
# Case 1: no trailing slash on source
rsync -av ~/project user@host:/dest/
# Copies ~/project ITSELF into /dest/ → /dest/project/

# Case 2: trailing slash on source
rsync -av ~/project/ user@host:/dest/
# Copies CONTENTS of ~/project into /dest/ → /dest/[contents]
```

This is subtle and the source of many mistakes. Remember: **trailing slash on source means copy contents; no trailing slash means copy the directory itself**.

**Dry-run before `--delete`:**

```bash
# ALWAYS do this first
rsync -avnz --delete source dest
# -n = dry run, show what would be deleted

# Only if the output looks right:
rsync -avz --delete source dest
```

Real example — nightly hardlinked backup:

```bash
#!/bin/bash
BACKUP_DIR=/mnt/backups
LATEST=$BACKUP_DIR/latest
DATED=$BACKUP_DIR/backup-$(date +%Y-%m-%d-%H%M%S)

# First backup (no hard-link)
if [ ! -d "$LATEST" ]; then
  rsync -avz --delete ~/data/ "$LATEST/"
else
  # Subsequent backups: hard-link unchanged files
  rsync -avz --delete --link-dest="$LATEST" ~/data/ "$DATED/"
  ln -sfn "$DATED" "$LATEST"
fi
```

This creates incremental backups where unchanged files are hard-linked (taking no additional space).

---

## 7 · Comparison Tables

### SCP vs SFTP vs rsync

| Dimension | SCP | SFTP | rsync |
|---|---|---|---|
| **Protocol** | SSH binary (legacy) or SFTP (OpenSSH 9+) | SFTP over SSH | rsync protocol over SSH |
| **Speed** | Depends on underlying protocol | Fast for random access | Fastest for large trees with small changes |
| **Incremental** | No — whole files | No | Yes — only transfers changed blocks |
| **Sync (bidirectional)** | No | No | No — but `--delete` makes one-way sync |
| **Batch mode** | Yes, easily (`scp file1 file2 ...`) | Yes, with script/batch | Yes, with large trees |
| **Interactive** | One-shot | Yes, like FTP | No, non-interactive |
| **Compression** | `-C` flag | Not built-in | `-z` flag |
| **Resume interrupted** | No | Yes, SFTP can resume | Yes (`--partial`), with care |
| **Complex filters** | No | No | Yes (`--exclude`, `--include`, regex) |
| **Preferred use** | Quick single files | Interactive file browse + move | Large syncs, backups, deploys |
| **When to choose** | Simple one-shot copy | Browsing remote FS, occasional files | Data centre migrations, backups |

### X11 forwarding: trusted vs untrusted

| Dimension | `-X` (untrusted) | `-Y` (trusted) |
|---|---|---|
| **How it works** | Remote X server connects back through SSH tunnel; local X server validates and filters | Remote X server connects through tunnel; no validation |
| **Security** | High — malicious app on remote cannot read your local clipboard or keystrokes | Lower — malicious remote app can read/inject input |
| **Use case** | Default; connecting to untrusted remote | You trust the remote server completely |
| **Common DISPLAY value** | `localhost:10.0` | `localhost:11.0` |
| **Speed** | Slightly slower (validation overhead) | Slightly faster |

Generally, use `-X` (the default) unless you know the remote is secure.

---

## 8 · Memory Tricks

> [!MEMORY]
> **"Ed25519: small, fast, modern — use it first."** If the system does not support Ed25519, fall back to RSA 4096. Never use DSA, ECDSA, or RSA 2048 for new keys.

> [!MEMORY]
> **"Permissions: 700 on `~/.ssh`, 600 on keys and `authorized_keys`."** SSH will refuse loose permissions. If auth fails mysteriously, check permissions first.

> [!MEMORY]
> **"Trailing slash on rsync source: include contents; no slash: include the directory."** This one mistake causes all the data-copy-in-wrong-place stories.

> [!MEMORY]
> **"SCP `-P` (capital); SSH `-p` (lowercase)."** Easy to mix up, maddening when you do.

> [!MEMORY]
> **"Known hosts stops MITM, agent forwarding enables it."** The host key check is your only defence against MITM. Agent forwarding (`-A`) can let a compromised bastion impersonate you.

> [!MEMORY]
> **"Port forwards: `-L` reaches things; `-R` exposes things; `-D` proxies everything."** Local forward reaches internal services; remote forward exposes your machine; dynamic forward becomes a SOCKS proxy.

---

## 9 · Interview Corner

<details>
<summary><strong>Beginner</strong> — Why is SSH better than telnet?</summary>

Telnet sends everything in cleartext: usernames, passwords, commands, output. An eavesdropper on the network reads it all. SSH encrypts the session, proves both sides' identity using cryptography, and lets you authenticate with keys instead of passwords. Telnet is 1980s technology; SSH is the only sane choice for remote admin.
</details>

<details>
<summary><strong>Beginner</strong> — What is the difference between a private key and a public key?</summary>

A private key is secret (kept on your machine) and proves your identity when you sign a challenge. A public key is shared widely and verifies that a signature could only come from someone with the corresponding private key. In SSH, the server has your public key in `authorized_keys`, and your client uses the private key to prove you are you. The private key is never sent to the server.
</details>

<details>
<summary><strong>Beginner</strong> — Which file holds the list of servers you have connected to?</summary>

`~/.ssh/known_hosts`. It contains entries like `example.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI...`. Each line is `hostname key_type public_key_blob`. SSH uses this to verify that the server is the one you expect, preventing MITM attacks.
</details>

<details>
<summary><strong>Beginner</strong> — What does `ssh-keygen -t ed25519` do?</summary>

Generates a new Ed25519 key pair: a private key (usually `~/.ssh/id_ed25519`) and a public key (`~/.ssh/id_ed25519.pub`). Ed25519 is modern, fast, and secure. You can optionally protect the private key with a passphrase.
</details>

<details>
<summary><strong>Intermediate</strong> — Why does SSH check the host key against `~/.ssh/known_hosts`?</summary>

To prevent man-in-the-middle attacks. If an attacker redirects your connection to their machine, they will present a different host key. SSH compares it against what you saw before; if it does not match, SSH aborts with "REMOTE HOST IDENTIFICATION HAS CHANGED." This is the only practical defence against MITM in SSH; if the host key changes, you must investigate.
</details>

<details>
<summary><strong>Intermediate</strong> — What do the permissions `600` on `~/.ssh/id_ed25519` protect against?</summary>

If the permissions are looser (e.g. `644`), other users or processes on the same machine could read your private key and impersonate you. SSH refuses to use keys with loose permissions, enforcing that only the owner can read the private key. This is why SSH will not log in and tells you to run `chmod 600`.
</details>

<details>
<summary><strong>Intermediate</strong> — How does `ssh-agent` improve usability without sacrificing security?</summary>

You set a strong passphrase on your private key. The first time you use it, you type the passphrase once; `ssh-agent` decrypts the key and caches it in memory. Subsequent SSH commands use the cached key without prompting. If your machine restarts, the agent is cleared; you enter the passphrase again. This balances security (strong passphrase) with usability (no re-typing).
</details>

<details>
<summary><strong>Intermediate</strong> — What is the difference between `-L` and `-R` in SSH port forwarding?</summary>

`-L` (local forward) opens a listening port on your machine and tunnels connections through to a remote internal service: `ssh -L 5432:db:5432 bastion` makes port 5432 local reachable to a DB on the internal network. `-R` (remote forward) opens a listening port on the remote machine and tunnels back to you: `ssh -R 8080:localhost:8080 remote` lets the remote server reach your local port 8080. One reaches inward; the other exposes outward.
</details>

<details>
<summary><strong>Intermediate</strong> — If a file size and modification time match, does rsync skip it?</summary>

By default, yes. rsync uses the `size-only` or modification time comparison, not checksums. If you fear a file was corrupted but kept the same size and timestamp, use `--checksum` to compare content hashes. This is slower but guarantees correctness.
</details>

<details>
<summary><strong>Advanced</strong> — Walk me through the SSH connection sequence from TCP to authenticated session.</summary>

1. TCP connect on port 22.
2. Both sides send version strings (SSH-2.0).
3. Both sides send `SSH_MSG_KEXINIT` listing supported algorithms.
4. Key exchange (Diffie-Hellman or ECDH): both sides derive a shared session key without sending it.
5. Each side computes a hash of the exchange; the server signs it with its host key.
6. The client retrieves the server's host key and verifies the signature. It also checks the host key against `~/.ssh/known_hosts`.
7. If the host key is unknown or changed, the client asks the user and either continues or disconnects.
8. Transport layer switches to using the session key with the negotiated cipher (AES-GCM, ChaCha20) and MAC.
9. Client sends `SSH_MSG_SERVICE_REQUEST` for user authentication.
10. Client sends `SSH_MSG_USERAUTH_REQUEST` with username and public-key signature (or password).
11. Server checks if the public key (or password) is authorized and sends success or failure.
12. If success, the client can open a channel for a shell or command.
</details>

<details>
<summary><strong>Advanced</strong> — Your SSH login hangs and eventually times out. What do you check?</summary>

1. Is the host reachable? `ping -c 1 example.com`.
2. Is the SSH port open? `nc -zv example.com 22` or `telnet example.com 22`.
3. Are you using the right username? `ssh -l alice example.com`.
4. Do you have network connectivity? `ip route`, `cat /etc/resolv.conf`.
5. Is the server's SSH daemon running? Log into it another way (console, different network, etc.) and check `systemctl status ssh`.
6. Is the firewall blocking? Check `sudo iptables -L` or cloud security group.
7. Are you behind a proxy? `ssh -vvv example.com` shows where it hangs.
8. Does `~/.ssh/config` have a `ProxyJump` that itself is unreachable? Test each hop.
</details>

<details>
<summary><strong>Advanced</strong> — How does rsync's rolling checksum and delta-transfer algorithm save bandwidth?</summary>

rsync does not transfer whole files. It splits large files into fixed-size blocks (typically 4 KB), computes a rolling hash for each block, and sends these hashes to the remote. The remote compares its hashes; for matching blocks, rsync sends nothing. For non-matching blocks, rsync sends the bytes that differ. This means a 1 GB file with a 1 KB change transfers only ~1 KB (plus metadata), not the whole file. The algorithm is complex (using weak hashes for speed and strong hashes for correctness), but the upshot is: incremental backups and large dataset syncs are orders of magnitude faster.
</details>

<details>
<summary><strong>Advanced</strong> — What is the security implication of `ssh -A` (agent forwarding) to an untrusted server?</summary>

When you use `-A`, the remote server can read your SSH agent socket and use your keys to authenticate to any other server your agent knows about. If the remote server is compromised, an attacker gains the ability to impersonate you to all your other systems. This is not a weakness in SSH; it is the intended behaviour, but it means you must trust the remote server completely. For multi-hop scenarios, prefer `ProxyJump` or `-J`, which do not expose your agent.
</details>

<details>
<summary><strong>Scenario</strong> — You deploy a CI/CD pipeline that needs to SSH to production servers. The pipeline has a private key, but you want to restrict what it can do. How do you set it up?</summary>

1. Generate a deploy key: `ssh-keygen -t ed25519 -f ~/.ssh/deploy_key -N ""` (no passphrase, since the CI system will use it).
2. On each production server, add a restricted entry to `~/.ssh/authorized_keys`:
   ```
   command="/opt/deploy.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding ssh-ed25519 AAAAC3... ci-deploy@build-001
   ```
3. Now, when the CI pipeline SSH's to the server, it can only run `/opt/deploy.sh`, not open a shell, and cannot forward ports or agents.
4. The pipeline stores the private key securely (in a secret store, not in the repo).
</details>

<details>
<summary><strong>Scenario</strong> — Your `known_hosts` file shows "REMOTE HOST IDENTIFICATION HAS CHANGED." Is this always an attack?</summary>

No, but investigate. Innocent causes:
1. The server's host key was regenerated (e.g. after an OS reinstall).
2. The IP address was reassigned to a different machine.
3. DNS misconfiguration (different IPs resolve to the same name now).
4. You are behind a proxy that is now presenting a different key.

**Dangerous cause:**
- A man-in-the-middle attack is redirecting your connection.

**Three-step response:**
1. Do not ignore it. Temporarily SSH to the host via a different route (console, second network, etc.) and check the host key. You can get it with `ssh-keyscan example.com`.
2. If the key is legitimate, remove it from `known_hosts`: `ssh-keygen -R example.com`.
3. SSH again; accept the new key.

**Hardening:** In production, use `StrictHostKeyChecking=accept-new` in config, which accepts new keys but still warns on changes. For scripted deploys, pre-populate `known_hosts` during server provisioning.
</details>

<details>
<summary><strong>Company style</strong> — We have a 10-minute session timeout. How do you keep SSH alive?</summary>

Set `ServerAliveInterval` in your `~/.ssh/config`:
```
Host *
    ServerAliveInterval 60
```

This sends a keep-alive packet every 60 seconds (adjust to be before the timeout). The connection stays open even if there is no activity. Alternatively, on the server, set `ClientAliveInterval 300` and `ClientAliveCountMax 2` in `/etc/ssh/sshd_config` (300 seconds, 2 missed packets before disconnect).
</details>

<details>
<summary><strong>HR style</strong> — Describe a time you had to troubleshoot an SSH connection that was failing.</summary>

A specific example: "A deployment script was failing because `ssh user@prod.internal` timed out. I ran `ssh -vvv user@prod.internal` to see debug output. The logs showed it was trying to use a key from the agent, but the key was not authorized on the server. I checked `~/.ssh/authorized_keys` and found the key was there, but the permissions were wrong (world-readable). I `chmod 600`'d it, and the connection worked. This taught me to always check permissions first, and to always run `-vvv` on connection issues." The lesson: systematic debugging, and knowing which tool (`ssh-add -l`, `ls -la`, `-vvv`) answers each question.
</details>

---

## 10 · Common Mistakes

> [!MISTAKE]
> **Using `-p` on `scp` (lowercase) instead of `-P` (capital).** `scp` uses capital `-P` for port; `ssh` uses lowercase `-p`. Beginners mix these up constantly. Remember: `scp` is special. One uppercase letter breaks the port forwarding.

> [!MISTAKE]
> **Forgetting the trailing slash on `rsync` source.** `rsync ~/project/ remote:/dest/` copies the *contents* of `project/` to `/dest/`. Without the slash, `rsync ~/project remote:/dest/` copies the `project` *directory itself* to `/dest/project/`. This is the single most frequent mistake in large data migrations.

> [!MISTAKE]
> **Running `rsync --delete` without `--dry-run` first.** The `--delete` flag removes files from the destination that do not exist in the source. A typo in the source path, a trailing slash error, or a stale destination will delete data. **Always** run `rsync -n --delete source dest` first and review the output.

> [!MISTAKE]
> **Leaving permissions loose on `~/.ssh/authorized_keys`.** If `authorized_keys` is world-writable, anyone on the system can add their own key and gain access. SSH will refuse to read a file with loose permissions. Set it to `600` with `chmod 600 ~/.ssh/authorized_keys`.

> [!MISTAKE]
> **Using `ssh -A` (agent forwarding) to servers you do not completely trust.** If the remote is compromised, the attacker has access to all your keys. Prefer `ProxyJump` for multi-hop scenarios.

> [!MISTAKE]
> **Not checking the host key fingerprint on first connection.** When SSH prompts "The authenticity of host ... can't be established," beginners mindlessly type `yes`. Attackers can intercept the connection before that prompt. **Always** verify the fingerprint out of band (call the sysadmin, check a trusted source) before accepting.

> [!DANGER]
> **Committing private keys to Git.** If you accidentally `git add ~/.ssh/id_ed25519`, the key is exposed forever in the repository history. Use `.gitignore` to exclude `~/.ssh/`, and use deploy keys (separate keys for CI systems) instead.

> [!DANGER]
> **Using a passphrased key in a script without `ssh-agent`.** If your script does `ssh -i ~/.ssh/key user@host`, and the key has a passphrase, the script will hang waiting for interactive input. Either use an unpassphrased deploy key (protected by file permissions) or use `ssh-agent` and `ssh-add` before running the script.

> [!DANGER]
> **Port forwarding to allow a remote server to reach a local database.** If you do `ssh -R 3306:localhost:3306 remote.example.com` and then someone logs into `remote.example.com`, they can now `curl localhost:3306` to reach your local database directly. This is intentional, but it is a tunnel, not permission control. Do not expose database ports this way to untrusted hosts.

---

## 11 · Summary & Mind Map

```mermaid
mindmap
  root(("SSH & Secure<br/>Transfer"))
    ("Why SSH exists")
      ("Telnet/FTP/rsh in cleartext")
      ("SSH: encrypted, authenticated")
      ("Only sane choice now")
    ("How SSH works")
      ("TCP connect")
      ("Version + algorithm negotiation")
      ("Key exchange (Diffie-Hellman)")
      ("Host key verification (known_hosts)")
      ("User authentication (key or password)")
      ("Encrypted session")
    ("Keys & Management")
      ("ssh-keygen -t ed25519")
      ("Private key: 600 permissions")
      ("~/.ssh/authorized_keys: 600")
      ("ssh-agent caches decrypted keys")
      ("ssh-copy-id deploys public key")
    ("SSH Client")
      ("~/.ssh/config: settings per host")
      ("ssh -i -p -l -o options")
      ("-L -R -D port forwarding")
      ("-J ProxyJump for multi-hop")
    ("SSH Server Security")
      ("/etc/ssh/sshd_config hardening")
      ("PermitRootLogin no")
      ("PasswordAuthentication no")
      ("fail2ban rate limiting")
      ("Lockout procedure: test before reload")
    ("File Transfer")
      ("scp: simple one-shot")
      ("sftp: interactive browse")
      ("rsync: delta, efficient syncs")
      ("rsync --delete: backup with cleanup")
    ("Production Patterns")
      ("Deploy keys: restricted, no passphrase")
      ("authorized_keys restrictions: command=")
      ("Agent forwarding: trust implications")
      ("Multiplexing: ControlMaster/ControlPersist")
```

**Ten sentences that carry the chapter.**

1. SSH encrypts remote login and file transfer, replacing cleartext telnet/FTP with authenticated, encrypted sessions.
2. The connection sequence is: TCP → version exchange → key exchange (deriving shared session key) → host key verification → user authentication → encrypted channel.
3. Your private key proves your identity; it is never sent to the server, only used to sign a challenge the server issues.
4. `~/.ssh/known_hosts` prevents MITM attacks by checking the server's host key matches what you saw before; if it changes, SSH aborts with a warning.
5. Ed25519 is modern, fast and small; use it for new keys; RSA 4096 is acceptable for legacy systems; DSA and RSA 2048 are obsolete.
6. File permissions on `~/.ssh/` (700) and private keys (600) are not optional — SSH refuses to use keys or read files with loose permissions.
7. `ssh-agent` caches decrypted keys in memory so you enter your passphrase once per session, not once per command.
8. SCP is one-shot; SFTP is interactive; rsync is for large syncs and incremental backups, using rolling checksums to transfer only changed blocks.
9. The trailing slash on rsync source changes the copy: with slash, copy contents; without slash, copy the directory.
10. Port forwarding (`-L`, `-R`, `-D`) lets you reach internal services, expose local ones, or use a SOCKS proxy through SSH; `ProxyJump` is safer for multi-hop than agent forwarding.

---

## 12 · Cheat Sheet

```diagram title="Chapter 12 — one-page revision"
GENERATE KEYS                    DEPLOY & USE
ssh-keygen -t ed25519            ssh-copy-id -i ~/.ssh/id_ed25519.pub user@host
ssh-keygen -t rsa -b 4096        ssh user@host [command]
ssh-add ~/.ssh/id_ed25519        ssh -i ~/.ssh/deploy_key user@host

PERMISSIONS (non-negotiable)     AGENT & PASSPHRASES
~/.ssh           700              eval "$(ssh-agent -s)"
~/.ssh/id_*      600              ssh-add ~/.ssh/key (prompts for passphrase)
~/.ssh/id_*.pub  644              ssh-add -l (list keys)
~/.ssh/authorized_keys    600     ssh-add -D (clear all)
~/.ssh/known_hosts        600

SSH CLIENT OPTIONS               PORT FORWARDING
-p port          remote port      -L local:host:remote   reach remote via local port
-i keyfile       private key      -R remote:host:local   expose local via remote port
-l user          username         -D port                SOCKS proxy through host
-N               no command       -J jump.host           ProxyJump through bastion
-f               background       -nf -L 5432:...       background tunnel

FILE TRANSFER                    RSYNC KEY OPTIONS
scp -P port -r -C file host:path  -a (archive: recursive, preserve all)
ssh-copy-id -i key user@host      -v (verbose)
sftp user@host                    -z (compress)
                                 -n (dry-run, always do this first)
                                 --delete (remove from dest if not in src)
                                 --exclude PATTERN

TRAILING SLASH RULE
rsync ~/src/ host:/dst/    → copies contents of src to /dst/[items]
rsync ~/src  host:/dst/    → copies src itself to /dst/src/

CONFIG FILE (~/.ssh/config)
Host prod
    HostName prod.example.com
    User ubuntu
    Port 2222
    IdentityFile ~/.ssh/prod_key
    ProxyJump bastion.example.com
    ServerAliveInterval 60
    ControlMaster auto
    ControlPath ~/.ssh/control-%h-%p-%r

KNOWN_HOSTS & SECURITY
~/.ssh/known_hosts            prevent MITM: one line per host
ssh-keygen -R example.com     remove host from known_hosts
StrictHostKeyChecking yes/accept-new/no    host key policy

TROUBLESHOOT CONNECTIONS
ssh -vvv user@host                   debug (very verbose)
ssh-keygen -l -f key                 key fingerprint
ssh-keyscan example.com              fetch remote host key
nc -zv example.com 22                check port is open
```

---

## 13 · Practice

### Flashcards

| Prompt | Answer |
|---|---|
| What does Ed25519 stand for in SSH context? | An elliptic-curve algorithm for public-key cryptography: fast, small (256 bits), modern and secure |
| Which file on the server holds authorized public keys? | `~/.ssh/authorized_keys` (or `~/.ssh/authorized_keys2` on older systems) |
| What is the correct permission on `~/.ssh/id_ed25519`? | 600 (rw-------) — SSH refuses to use keys with looser permissions |
| Does your private key ever leave your machine during SSH auth? | No. It only signs a challenge issued by the server; the private key never travels over the network |
| Which command caches decrypted keys so you do not type passphrases repeatedly? | `ssh-agent` (caches in memory); `ssh-add` adds keys to it |
| What does `ssh -L 5432:localhost:5432 host` do? | Opens local port 5432, tunnels connections through SSH to `host`, then to `localhost:5432` on the remote |
| What does `ssh -R 8080:localhost:8080 host` do? | Opens port 8080 on `host`, tunnels connections through SSH back to your local `localhost:8080` |
| Name the three phases of SSH connection sequence | 1. Transport (TCP, version negotiation); 2. Key exchange (derive session key); 3. Authentication (user auth) |
| What does `~/.ssh/known_hosts` protect against? | MITM attacks — verifies that the server's host key matches what you saw before |
| What is the difference between `-p` (ssh) and `-P` (scp)? | `ssh -p 2222` uses port 2222; `scp -P 2222` uses port 2222. Easy to mix up, and a common mistake |
| What does `rsync -avz --delete source dest` do? | Copies `source` to `dest` recursively, preserving permissions, compressing, and **deleting files in `dest` that do not exist in `source`** |
| What is the trailing slash rule in rsync? | With slash: copy contents; no slash: copy the directory itself. `src/ → dst/contents` vs `src → dst/src` |
| Which SSH flag enables agent forwarding to a remote host? | `-A` — but only use on hosts you completely trust, as the remote can impersonate you to other systems |
| What command removes a host from `~/.ssh/known_hosts`? | `ssh-keygen -R example.com` |
| When does SSH warn "REMOTE HOST IDENTIFICATION HAS CHANGED"? | When the server's host key differs from the one in `known_hosts`. Could be legitimate (key regeneration) or a MITM attack; investigate |

### Multiple choice

1. Which command generates a new Ed25519 key pair? **(a)** `ssh-keygen -t rsa` **(b)** `ssh-keygen -t ed25519` **(c)** `ssh-key-create ed25519` **(d)** `ssh ed25519 key-gen`
2. What is the correct permission for `~/.ssh/id_ed25519`? **(a)** 644 **(b)** 755 **(c)** 600 **(d)** 777
3. If `authorized_keys` is world-writable, SSH will: **(a)** accept it and warn **(b)** use it but log an error **(c)** refuse to read it, denying login **(d)** strip world permissions automatically
4. What does `ssh -vvv user@host` provide? **(a)** Three simultaneous connections **(b)** Very verbose debug output **(c)** Triple encryption **(d)** Three parallel port forwards
5. The SSH host key is checked against: **(a)** `/etc/ssh/ssh_config` **(b)** `~/.ssh/known_hosts` **(c)** `/etc/ssh/sshd_config` **(d)** `~/.ssh/authorized_keys`
6. `scp -P port` uses capital `-P` because: **(a)** `scp` is old and predates convention **(b)** lowercase `-p` means preserve time/perms **(c)** OpenSSH designers wanted it different **(d)** `-p` is reserved for another protocol
7. For rsync, `--dry-run` with `--delete` is important because: **(a)** it prevents actual deletion on first run **(b)** it shows what would be deleted so you verify **(c)** it reverses the operation **(d)** it runs in "safe mode"
8. If you use `ssh -A` to a compromised server, an attacker can: **(a)** only read your SSH keys **(b)** impersonate you to other systems your agent knows about **(c)** do nothing — agent forwarding has no risks **(d)** access your terminal history
9. `ssh -L 5432:db:5432 bastion` — what does `db` resolve as? **(a)** your local machine **(b)** the bastion server's perspective (internal network) **(c)** a public DNS name **(d)** must be an IP address
10. The trailing slash in `rsync ~/src/ host:/dst/` means: **(a)** copy the src directory **(b)** copy src's contents; do not create src/ on remote **(c)** use relative paths **(d)** do not follow symlinks

<details>
<summary>Answers</summary>

1. (b) — `ssh-keygen -t ed25519`.
2. (c) — 600 (owner read/write only).
3. (c) — SSH refuses to read files with loose permissions.
4. (b) — Very verbose debug output.
5. (b) — `~/.ssh/known_hosts`.
6. (b) — lowercase `-p` preserves file modification times and permissions in scp.
7. (b) — shows what would be deleted; prevents accidents.
8. (b) — agent forwarding allows the remote to use your cached keys.
9. (b) — from the bastion's perspective, it resolves via the internal network or hosts file.
10. (b) — trailing slash on source copies contents; without it, copies the directory itself.

</details>

### Fill in the blanks

1. The default SSH port is ______ .
2. A private key should never be ______ to the server.
3. The SSH client checks the server's key against ______ to detect MITM attacks.
4. Ed25519 keys are ______ bits and use ______ -curve cryptography.
5. To add your public key to a server without a password, use ______ ______ .
6. The file `~/.ssh/config` lets you define ______ -specific settings.
7. In rsync, the ______ ______ determines whether you copy the directory or its contents.
8. A deploy key should have a ______ passphrase (or none) and restricted ______ in `authorized_keys`.
9. `ssh-agent` caches ______ keys so you type the ______ once per session.
10. Using `ssh -A` to an untrusted server exposes your ______ to impersonation.

<details>
<summary>Answers</summary>

1. 22 — 2. sent — 3. `~/.ssh/known_hosts` — 4. 256, elliptic — 5. ssh-copy-id — 6. host — 7. trailing slash — 8. empty (no) ; command= ; 9. decrypted ; passphrase — 10. keys (or credentials).

</details>

### True or false

1. Your SSH private key must always be protected with a passphrase.
2. SSH will refuse to use a private key with permissions 644.
3. The server stores a copy of your private key in `authorized_keys`.
4. `ssh -p 22 -i key user@host` and `scp -P 22 -i key file user@host:/` use the same port flag syntax.
5. If the host key in `known_hosts` changes, SSH always aborts; it never connects.
6. `rsync` transfers entire files, even if only one byte changes.
7. The trailing slash in rsync makes a difference: `src/` vs `src` copy different things.
8. Agent forwarding (`-A`) is always safe because SSH has built-in protections.
9. Deploy keys should be passphrased so CI systems do not accidentally expose them.
10. `StrictHostKeyChecking=accept-new` adds new host keys but warns if they change.

<details>
<summary>Answers</summary>

1. **False** — a passphrase is recommended but not required. You can generate keys with no passphrase for automation.
2. **True** — SSH refuses permissions looser than 600 on private keys.
3. **False** — the server stores your *public* key in `authorized_keys`. Private keys never leave your machine.
4. **False** — `ssh` uses lowercase `-p` and `scp` uses capital `-P`.
5. **False** — if the key is unknown, SSH prompts; if it changed, it warns but you can investigate and continue.
6. **False** — rsync uses rolling checksums to detect changed blocks and only transfers those.
7. **True** — this is the critical trailing slash rule.
8. **False** — if a compromised remote server can access your agent socket, it can impersonate you to other systems.
9. **False** — deploy keys should have *no* passphrase (or a passphrase in a secret store) so CI systems can use them unattended.
10. **True** — `accept-new` adds unknown keys; still warns on changes.

</details>

### Hands-on lab

Do these on a lab VM (or two VMs for multi-hop scenarios).

1. **Generate a key pair.** Run `ssh-keygen -t ed25519 -C "lab@test"` and store it in `~/.ssh/lab_key`. Set a passphrase. Then view the public key with `ssh-keygen -y -f ~/.ssh/lab_key` and verify it matches `~/.ssh/lab_key.pub`.
2. **Deploy a public key to another machine.** On a second VM, run `ssh-copy-id -i ~/.ssh/lab_key alice@192.168.1.X`. SSH back without a password to verify. Check `~/.ssh/authorized_keys` on the remote to see your key was added.
3. **Manually break and fix permissions.** `chmod 644 ~/.ssh/lab_key` and try `ssh -i ~/.ssh/lab_key alice@192.168.1.X`. Observe the error. Fix it: `chmod 600 ~/.ssh/lab_key`. Retry and confirm it works.
4. **Host key mismatch simulation.** Add a bogus entry to `~/.ssh/known_hosts` for a server you will SSH to. Then SSH to it and observe "REMOTE HOST IDENTIFICATION HAS CHANGED." Remove it with `ssh-keygen -R` and retry.
5. **Port forwarding to an internal service.** On VM2, run a simple HTTP server: `python3 -m http.server 8000`. From VM1, use `ssh -L 9000:localhost:8000 user@vm2`, then `curl localhost:9000`. Confirm you reach VM2's service through the tunnel.
6. **SFTP batch operations.** Create a file with SFTP commands:
   ```
   cd /tmp
   put ~/file.txt
   quit
   ```
   Run `sftp -b cmds.txt user@host` and verify the file was uploaded.
7. **Rsync with dry-run and `--delete`.** Sync a directory, then delete a file from the source. Run `rsync -avnz --delete source user@host:/dest` and observe which files would be deleted. Verify correctness, then remove `-n` and sync for real.
8. **SSH multiplexing (ControlMaster).** Add to `~/.ssh/config`:
   ```
   Host *
       ControlMaster auto
       ControlPath ~/.ssh/control-%h-%p-%r
       ControlPersist 600
   ```
   Then run `ssh user@host` twice in quick succession; the second should be instant (reusing the first connection).

### Challenge problems

1. You have a CI/CD system that needs to deploy to 10 production servers. Design a secure key distribution strategy: which key type, passphrase policy, and `authorized_keys` restrictions would you use to minimize blast radius if one CI system is compromised?
2. A teammate is syncing a large codebase with `rsync` but occasionally files disappear from the destination. Investigate: what questions would you ask, and how would you design a safer sync procedure?
3. You need to SSH to a server behind a NAT; you only have outbound SSH access from the NAT-ed server to your bastion. Design a reverse tunnel setup (using `-R`) that lets you SSH inward. What are the security implications?
4. Your team is migrating terabytes of data between two data centres. Design an rsync command with intermediate verification, compression, rate limiting, and recovery from interruption. Write a shell script that resumes if interrupted.
5. Investigate the "REMOTE HOST IDENTIFICATION HAS CHANGED" scenario: research the three innocent causes and the one dangerous one. Write a decision tree for what to do in each case.
6. Set up SSH agent forwarding through three servers (A → B → C) and demonstrate where the agent socket is accessible and where it is not. Explain the security boundary.
7. Harden `/etc/ssh/sshd_config` on a test VM: disable password auth, set specific algorithms, rate-limit login attempts, and configure logging. Verify each setting with `sshd -t`.
8. Compare SCP vs SFTP vs rsync on a test VM by transferring a large file with 1% changed, then 10% changed, then 50% changed. Measure bandwidth and time for each tool.
9. Write a monitoring script that alerts if someone logs into a server via SSH with a password (using `grep` on `/var/log/auth.log`). Design it to be robust against log rotation.
10. Design an SSH bastion architecture for a company with 200 production servers: key distribution, audit logging, fail2ban rules, and CI/CD access patterns.

> [!NOTE]
> **Where to go next.** Chapter 13 covers firewalls, network security, and filtering — how to allow SSH in while blocking attacks. Chapter 14 dives into VPNs and tunnelling technologies that build on the SSH primitives you have learned here.

