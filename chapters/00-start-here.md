---
part: 0
part_title: Start here
number: 00
title: How to Use This Handbook
tagline: What this is, how it differs from the notes it replaces, and the fastest route through it for exams, interviews and real work.
source: Rebuilt from CloudandDevops_Notes.pdf
minutes: 8
---

## 1 · What this is

This is a rebuilt replacement for a 326-page trainer PDF covering Linux, virtualization, system administration and Docker. It is **not** a summary of that PDF. The PDF was used only as a syllabus — a list of what must be covered — and then every explanation was rewritten from scratch, at greater depth, with the missing prerequisites filled in, the errors corrected, and the diagrams redrawn.

Three things make it different from the notes it replaces.

**It teaches, rather than listing.** The original gives `ls` two options and one example. Here, every command carries its purpose, full option table, several worked examples, real output explained field by field, the way professionals actually use it, the mistakes people make, and how it differs on BSD or macOS.

**It covers the hidden syllabus.** The source PDF ends with 495 multiple-choice questions spanning filesystems, LVM, RAID, NFS, SSH hardening, ACLs, `sudoers`, LDAP, cron and the boot process — none of which its prose ever teaches. Roughly 40% of that question bank was unanswerable from the notes themselves. Those topics are taught here as full chapters.

**It corrects the source.** Where the original is wrong, this handbook says so in a bordered callout rather than silently repeating the error. The corrections so far include the claim that macOS and PlayStation OS derive from Linux (they derive from BSD and Mach), the release year of Linux 6.0, a section on `rmdir` that duplicates `mkdir`'s text verbatim, the meaning of `file -k`, `du -M`, and the description of `kill -9` as an "option" rather than a signal.

> [!NOTE]
> Every chapter names the PDF pages it derives from in its header plate, so you can always trace a passage back to the original syllabus.

---

## 2 · How to read the reader

| Action | How |
|---|---|
| Search everything | Press <kbd>/</kbd> anywhere, then type. Arrow keys to move, <kbd>Enter</kbd> to jump |
| Next / previous chapter | <kbd>]</kbd> and <kbd>[</kbd> |
| Jump to a section | The outline rail on the right tracks where you are |
| Copy a command | The `copy` button on any code panel |
| Switch light / dark | The dial in the top-right corner |
| Link to a passage | Hover any heading and click the `#` |
| Print or export to PDF | <kbd>Ctrl</kbd>+<kbd>P</kbd> — every chapter prints, expanded, in order |

Four kinds of panel appear throughout, and they mean different things:

```bash
# A command panel. This is something you type.
uname -r
```

```console
$ uname -r
6.8.0-45-generic
```

A terminal panel is darker and shows a transcript — the command *and* its real output. The `$` marks what you typed; everything else came back from the machine.

```diagram title="A diagram panel"
   ┌──────────────┐         ┌──────────────┐
   │  monospace   │────────▶│  ASCII art   │
   └──────────────┘         └──────────────┘
```

Mermaid panels render as real diagrams — flowcharts, sequence diagrams, timelines and mind maps.

Callouts are graded, and the grading is meaningful:

> [!TIP]
> A better way to do something, or the shortcut professionals actually use.

> [!MISTAKE]
> The specific wrong thing learners do here. Read these; they are drawn from real failures.

> [!DANGER]
> This command destroys data or breaks systems. Linux has no undo and no recycle bin.

> [!EXAM]
> A one-mark answer, in the exact phrasing to memorise.

> [!INTERVIEW]
> This is a question you will actually be asked, near-verbatim.

---

## 3 · The map

The handbook is built in seven parts, each readable independently. Chapters that are still being written are marked; the rest are complete.

<dl>
<dt>Part I — Foundations</dt>
<dd><strong>01 Introduction to Linux</strong> · what an operating system does, kernel vs distribution, the Unix lineage, POSIX, GPL, and how to fingerprint any machine you are dropped onto.<br>
<strong>02 Virtualization &amp; Virtual Machines</strong> · hypervisor types, full vs paravirtualization, VM networking modes, VirtualBox/VMware/KVM from the command line, and building the throwaway lab machine that every later chapter assumes.</dd>

<dt>Part II — Working in the Shell</dt>
<dd><strong>03 Shells &amp; Terminals</strong> · terminal vs shell, TTYs and PTYs, startup file order, aliases, functions, environment variables, history, prompts, redirection and quoting.<br>
<strong>04 Files &amp; Directories</strong> · the filesystem tree, and <code>ls pwd cd mkdir rmdir rm cp mv touch file ln locate find</code> in full.<br>
<strong>05 Text Processing &amp; Searching</strong> · streams and pipes, then <code>cat less head tail grep sed awk sort uniq cut tr wc diff tee echo printf xargs</code>, plus survivable <code>vi</code>.<br>
<strong>06 Archiving &amp; Compression</strong> · archiving vs compression, <code>tar</code> in depth, <code>zip/unzip</code>, and gzip vs bzip2 vs xz vs zstd.</dd>

<dt>Part III — System Internals</dt>
<dd><strong>07 Filesystems, Mounting &amp; the FHS</strong> · inodes, journalling, filesystem types, <code>mkfs</code>, <code>mount</code>, <code>/etc/fstab</code>, <code>fsck</code>, <code>df</code> vs <code>du</code>, swap and NFS.<br>
<strong>08 Disks, Partitioning, LVM &amp; RAID</strong> · the storage stack, MBR vs GPT, <code>fdisk</code>/<code>parted</code>, LVM end to end, and every RAID level.<br>
<strong>09 Processes, Signals &amp; Services</strong> · fork and exec, process states, zombies, the full signal table, <code>ps</code>/<code>top</code>, nice, jobs, and writing your own systemd unit.<br>
<strong>10 The Boot Process</strong> · firmware to login prompt, GRUB, initramfs, targets and runlevels. <em>In progress.</em></dd>

<dt>Part IV — Networking &amp; Remote Access</dt>
<dd><strong>11 Linux Networking</strong> · addressing, subnets, routing, DNS, ports, and the <code>ip</code>/<code>ss</code>/<code>dig</code>/<code>curl</code> toolkit. <em>In progress.</em><br>
<strong>12 SSH &amp; Secure Transfer</strong> · key authentication, <code>ssh-agent</code>, hardening <code>sshd_config</code>, tunnels, <code>scp</code> and <code>rsync</code>. <em>In progress.</em></dd>

<dt>Part V — System Administration</dt>
<dd><strong>13 Users, Permissions, ACLs &amp; sudo</strong> · the permission model, <code>umask</code>, setuid/setgid/sticky, ACLs and <code>sudoers</code>. <em>In progress.</em><br>
<strong>14 Package Management</strong> · <code>apt</code>/<code>dpkg</code>, <code>dnf</code>/<code>yum</code>/<code>rpm</code>, repositories and building from source. <em>In progress.</em><br>
<strong>15 Logs, Monitoring &amp; Scheduling</strong> · <code>journalctl</code>, rsyslog, logrotate, cron, <code>at</code>, systemd timers and the monitoring toolkit. <em>In progress.</em><br>
<strong>16 Directory Services with LDAP</strong> · DNs, LDIF, objectClasses, ports 389 and 636. <em>In progress.</em></dd>

<dt>Part VI — Automation</dt>
<dd><strong>17 Bash Scripting</strong> · from shebang to <code>set -euo pipefail</code>, with the quoting and exit-code discipline that separates working scripts from dangerous ones. <em>In progress.</em><br>
<strong>18 The Automation Script Library</strong> · the source PDF's 25 production scripts, rebuilt, explained line by line and hardened. <em>In progress.</em></dd>

<dt>Part VII — Containers</dt>
<dd><strong>19 Containers &amp; Docker</strong> · namespaces and cgroups, images and layers, Dockerfiles, networking, volumes, Compose, Podman and production practice. <em>In progress.</em></dd>
</dl>

---

## 4 · Before anything else: build the lab

You cannot learn this material by reading it. Almost every chapter ends in a hands-on lab, and several of them are destructive on purpose — you will fill a disk, break `/etc/fstab`, kill the wrong process and recover from it.

So the first practical task is a virtual machine you are free to ruin:

1. Install **VirtualBox** on your laptop (Chapter 2 covers hypervisor choice, and why a Type 2 hypervisor is right for a learning lab).
2. Create a VM with 2 vCPUs, 4 GB RAM and a 25 GB disk, and install **Ubuntu Server LTS** — no desktop.
3. Set networking to NAT and forward host port 2222 to guest port 22, so you can `ssh -p 2222 user@127.0.0.1` from a real terminal instead of the VirtualBox console window.
4. **Take a snapshot immediately** and call it `clean-install`. Every time a lab wrecks the machine, roll back to it in seconds.

Chapter 2 gives the exact commands for all four steps.

> [!TIP]
> Do the labs in a real terminal over SSH, not in the hypervisor's console window. Copy-paste, scrollback and multiple tabs make an enormous difference, and it is how you will work professionally.

---

## 5 · Three routes through it

Pick the route that matches why you are here. All three assume you do the labs.

**For a university exam.** Read Chapters 1, 2, 3 and 7 closely — definitions, comparison tables and the `> [!EXAM]` callouts are written for you. Then work the Practice section of every chapter: the MCQs, fill-in-the-blanks and true/false questions are modelled on the source PDF's own 495-question bank. Memorise the cheat sheets last, the week before the paper.

**For an interview.** Go straight to the Interview Corner of every chapter and answer each question out loud *before* opening the model answer. Prioritise Chapters 9 (processes and signals), 7 (filesystems), 13 (permissions), 11 (networking) and 19 (Docker) — in practice that is where the questions come from. The scenario questions matter more than the definitions: being handed an unfamiliar server and knowing your first five commands is the thing that gets people hired.

**For real work.** Read Part II properly, then use the rest as reference — search is there for exactly this. Read Chapter 17 before you write any script that runs unattended, and Chapter 9's systemd section before you deploy anything that must survive a reboot.

> [!MEMORY]
> If you only ever retain one thing from this handbook, retain the debugging reflex: **check the logs, check the disk, check the permissions, check the process, check the network — in that order.** Most production incidents are one of those five, and the order is roughly how often each is the culprit.

---

## 6 · A note on honesty

The source PDF was described as covering Kubernetes, Cloud and DevOps across hundreds of pages. It does not. Kubernetes appears six times, AWS three, and Jenkins thirteen — all as short shell snippets inside its automation-scripts chapter. There is no Terraform, Ansible, Helm, Prometheus, Git or CI/CD content in it, and no cloud-architecture material. Docker is the only container technology it teaches properly.

This handbook covers that syllabus faithfully and improves it. Where a topic is genuinely absent from the source, it says so rather than pretending otherwise, and points you at what to study next.

> [!NOTE]
> Start with **Chapter 1**, or jump straight to **Chapter 2** if you want the lab running first.
