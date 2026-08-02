---
part: VI
part_title: Automation
number: 17
title: Bash Scripting
tagline: From one-liners to production-grade scripts — how to write shell code that does not destroy your system, handles errors correctly, and runs reliably at 3 a.m.
source: PDF p145–162 quiz bank
minutes: 55
---

## 1 · The Big Picture

### Why this topic exists

You have typed one-liners in Bash: `ls -la | grep ".txt"`. You have run commands sequentially in the shell. But a shell script is different. It is a program — it must handle errors, work with variables, loop over data, make decisions, and run correctly the first time on a machine you have never touched before.

The difference between a working script and a dangerous one is not intelligence; it is discipline. Four specific practices prevent 99% of production script failures:

1. **`set -euo pipefail`** at the top — stop on error, undefined variable, or pipe failure
2. **Always quote variables:** `"$var"` not `$var`
3. **Always use `find` or `while read` instead of `ls` in a loop**
4. **Always test with `bash -x` and `set -x`**

Learn these first. The rest is syntax.

### The real problem it solves

Imagine you write a script to back up important files:

```bash
#!/bin/bash
for file in $(ls /important/data); do
  cp /important/data/$file /backup/$file
done
```

On Friday it works. On Monday, someone adds a file with a space in the name. The loop breaks. You copy the file to the wrong location. Or you forget to check if the backup succeeded, and later discover your backups have been corrupted for six months.

Or you write a deployment script that does not set `-e`, and a `docker build` fails silently, but the script continues and deploys the old image.

Production scripts must:
- **Fail loudly** when any command fails
- **Never silently drop variables**
- **Parse filenames correctly**, even with spaces
- **Handle signals** (SIGTERM, SIGINT) gracefully
- **Log what they are doing**
- **Be testable** — you must watch the exact commands being run

### Where you will encounter it

| Context | What scripts are doing there |
|---|---|
| **System administration** | Backups, log rotation, user provisioning, system health checks |
| **CI/CD pipelines** | Build, test, and deploy scripts; health checks before rollout |
| **Container entrypoints** | Every Docker container you run that is not a compiled binary has a shell script as PID 1 |
| **Cron jobs** | Automated tasks that run on a schedule — backups, database maintenance, reporting |
| **Infrastructure automation** | Pre-deployment checks, post-deployment validation, rollback logic |
| **DevOps tooling** | Terraform pre/post hooks, Ansible playbooks often contain shell modules |
| **Embedded systems** | IoT devices, network appliances, and embedded Linux all use shell scripts for configuration |

### Why companies care

- **Reliability** — scripts that crash or drop errors cause outages. A single silent failure can cost days to debug.
- **Auditability** — logs from scripts answer "what changed and when" for compliance and incident response.
- **Portability** — shell scripts run on any Linux system with bash. Deployment across 1,000 servers is one `scp` plus 1,000 SSH invocations.
- **Debuggability** — when a script fails at 3 a.m., you need to see exactly what it ran (`bash -x` output in logs).

---

## 2 · Intuition First

### The script as a checklist

A shell script is a checklist that a computer runs. Each line is a step:

1. Open the log file
2. Copy the backup
3. Compress it
4. Upload it to S3
5. Delete the local copy
6. Email the admin

But unlike a human checklist, a computer follows it *literally*. If you forget to specify "stop if any step fails," the computer will keep going even if step 3 (compress) fails. You end up uploading a corrupt file.

The `set -e` option makes the script ask the computer: "Stop if any step fails."

### The quoting discipline

In English, we understand context:

> "Alice said the word 'hello' in the file /tmp/test.txt"

A computer does not. If you write:

```bash
file="hello world.txt"
cp $file /backup
```

The computer hears: "copy the file 'hello', the file 'world.txt', and '/backup'." (Three arguments, not two.)

If you write:

```bash
cp "$file" /backup
```

The computer hears: "copy the file 'hello world.txt'." (Two arguments, as you intended.)

**Quote variables unless you have a specific reason not to.** You will never regret it.

### Why `ls` in a loop breaks

A common pattern:

```bash
for file in $(ls /data); do
  process "$file"
done
```

If `/data/file one.txt` exists, `ls` outputs:

```
file
one.txt
```

The loop iterates twice, trying to process a file named "file" (not found) and "one.txt" (not found). The real file "file one.txt" is never processed.

If you use:

```bash
find /data -type f -print0 | while IFS= read -rd '' file; do
  process "$file"
done
```

It handles any filename correctly — even filenames with newlines, spaces, and special characters.

---

## 3 · Technical Definitions

**Shell script.** A plain text file containing shell commands, executed line by line by the shell. Typically starts with a `shebang` line (`#!/bin/bash`). Run with `bash script.sh`, `sh script.sh`, or `./script.sh` (requires the script to be executable, with `chmod +x`).

**Shebang (hashbang).** The first line of a script, beginning with `#!`, followed by the path to an interpreter. Examples:

| Shebang | Meaning |
|---|---|
| `#!/bin/bash` | Use Bash from `/bin/bash`; not portable if Bash is at `/usr/local/bin/bash` |
| `#!/usr/bin/env bash` | Search `$PATH` for `bash`; more portable, the preferred approach |
| `#!/bin/sh` | Use POSIX shell (stricter, more portable, but fewer features) |
| `#!/usr/bin/env python3` | Use Python; the file extension `.py` is not required |

The shebang is not a comment; it is metadata that tells the kernel which interpreter to use when you execute the script directly (`./script.sh`).

**Exit code (exit status).** Every command returns a number: 0 means success, 1–255 means failure. Bash stores it in `$?`.

```console
$ ls /nonexistent 2>&1
ls: cannot access '/nonexistent': No such file or directory
$ echo $?
2
```

**Variable.** A name-value pair. Assignment (no spaces around `=`):

```bash
name="Alice"
count=42
flag=true
```

Expansion (always quote):

```bash
echo "$name"        # Alice
echo "${name}"      # Alice (same, more explicit)
echo "$count"       # 42
```

**Parameter expansion.** Syntax for accessing variables with optional defaults, transformations, or error checking:

| Syntax | Meaning | Example |
|---|---|---|
| `$var` or `${var}` | Value of `var` | `${user}` → `alice` |
| `${var:-default}` | Value of `var`, or `default` if unset | `${editor:-vim}` → `vim` (if `editor` is unset) |
| `${var:=default}` | Value of `var`, or set `var` to `default` if unset | `${logdir:=/var/log}` → sets `logdir` |
| `${var:?error}` | Value of `var`, or error and exit if unset | `${required:?missing input}` → exits if `required` is unset |
| `${var##pattern}` | Remove longest match of `pattern` from start | `${file##*/}` removes path, leaving filename |
| `${var%%pattern}` | Remove longest match of `pattern` from end | `${file%%.*}` removes extension |
| `${#var}` | Length of `var` | `${#name}` → `5` (if `name="Alice"`) |

**Quoting rules.** Three types:

| Type | Behavior | Example |
|---|---|---|
| Double quotes `"..."` | Expansions and command substitutions work; single `\` escapes special chars | `"$var"`, `"$(cmd)"` both expand |
| Single quotes `'...'` | Nothing expands; literal string | `'$var'` is the string `$var`, not its value |
| `$'...'` | ANSI-C quoting; interprets escape sequences like `\n`, `\t`, `\"` | `$'line1\nline2'` creates a newline |

**Special variables.** Always available:

| Variable | Meaning |
|---|---|
| `$0` | Name of the script itself (`script.sh`) |
| `$1, $2, ...` | Command-line arguments (first, second, etc.) |
| `$@` | All arguments as separate words; must quote: `"$@"` expands to `"$1" "$2" ...` |
| `$*` | All arguments as one string; almost never what you want |
| `$#` | Number of arguments |
| `$?` | Exit code of the last command |
| `$$` | Process ID (PID) of the script itself |
| `$!` | PID of the last background process |
| `$-` | Options currently set (e.g., `eui`) |
| `$_` | Last argument of the previous command |

### The philosophy: "Write it as if it will fail"

Every command in a production script should be written assuming:
- The file does not exist
- The directory does not have write permission
- The network is slow
- A signal (SIGTERM) arrives mid-execution

This is not paranoia; it is professionalism.

---

## 4 · Internal Working

### How Bash parses and executes a line

```mermaid
flowchart TB
    A["User types: ls -la \"/home/alice/my files\"] --> B["1. Lexing<br/>Split into tokens, respecting quotes"]
    B --> C["2. Expansion<br/>Substitute \$var, \$(cmd), etc."]
    C --> D["3. Quote removal<br/>Strip quotes, leaving bare string"]
    D --> E["4. Globbing<br/>Expand * ? if no quotes"]
    E --> F["5. Word splitting<br/>Split on IFS=unquoted spaces"]
    F --> G["6. Command lookup<br/>Find ls in PATH"]
    G --> H["7. Execution<br/>fork + execve"]
    H --> I["8. Wait<br/>Parent waits for child"]
    I --> J["9. Exit code<br/>Store in \$?"]
```

This explains many errors. For example:

```bash
file="/tmp/test file.txt"
cp $file /backup          # WRONG: $file expands to /tmp/test file.txt
                          # Then word-split into /tmp/test, file.txt, /backup — 3 args to cp
cp "$file" /backup        # RIGHT: expands to /tmp/test file.txt, one argument
```

### Variable scope and subshells

Every pipe creates a **subshell** — a child Bash process. Variables set in a subshell do not affect the parent:

```bash
count=0
echo "line1" | while read line; do
  ((count++))
  echo "count is $count"         # Prints 1
done
echo "After loop, count=$count"  # Prints 0 (!!!)
```

Why? The `while read` runs in a subshell (because of the pipe). The `((count++))` increments the subshell's copy, not the parent's.

Fix: avoid pipes to loops, or use process substitution:

```bash
count=0
while read line; do
  ((count++))
  echo "count is $count"
done < <(echo "line1")
echo "After loop, count=$count"  # Now prints 1
```

### Exit codes and the pipeline

In Bash, a pipeline's exit code is **the exit code of the last command** by default:

```bash
false | true
echo $?     # 0 (true's exit code)
```

This hides failures in earlier commands. `set -o pipefail` changes this:

```bash
set -o pipefail
false | true
echo $?     # 1 (false's exit code is now visible)
```

**This is why `set -euo pipefail` is the first line of every production script.**

### How `set` options work

`set` enables or disables Bash options. The critical ones:

| Option | Long form | Meaning | Use case |
|---|---|---|---|
| `-e` | `errexit` | Exit if any command fails | Stop on error |
| `-u` | `nounset` | Error if undefined variable is expanded | Catch typos in variable names |
| `-o pipefail` | `pipefail` | Fail if any command in a pipe fails | Catch mid-pipeline errors |
| `-x` | `xtrace` | Print each command before executing it | Debugging |

```bash
#!/bin/bash
set -euo pipefail     # All three: error, nounset, pipefail

undefined_var=$nonexistent    # Error: nonexistent: unbound variable
false | true                   # Error: false's failure is caught
```

### Error handling with `trap`

A `trap` is a signal handler. Common signals:

| Signal | Meaning | Trigger |
|---|---|---|
| `EXIT` | Script is exiting (normal or error) | Always runs, even on `set -e` error |
| `SIGTERM` | Graceful termination request | `kill -TERM $pid` |
| `SIGINT` | Interrupt (Ctrl+C) | User presses Ctrl+C |
| `ERR` | A command failed (only if `set -E`) | Any command with non-zero exit |

Example: ensure cleanup always runs:

```bash
#!/bin/bash
set -euo pipefail

cleanup() {
  echo "Cleaning up..."
  rm -f /tmp/working_file
  echo "Done"
}

trap cleanup EXIT

# Your script code here
cp /important/file /tmp/working_file
# If the script exits (normally or via error), cleanup() runs
```

---

## 5 · Real Examples

### Example 1: Simple file backup (beginner)

```bash
#!/usr/bin/env bash
set -euo pipefail

# Back up a directory with a timestamp
source_dir="/home/alice/data"
backup_dir="/backup/$(date +%Y-%m-%d_%H-%M-%S)"

mkdir -p "$backup_dir"
cp -r "$source_dir"/* "$backup_dir/"

echo "Backup complete: $backup_dir"
```

**Issues with this script:**
- Does not check if `$source_dir` exists
- Does not check disk space
- No error message if `mkdir` fails
- Does not log the action

### Example 2: Robust file backup (intermediate)

```bash
#!/usr/bin/env bash
set -euo pipefail

readonly source_dir="/home/alice/data"
readonly backup_dir="/backup"
readonly timestamp="$(date +%Y-%m-%d_%H-%M-%S)"
readonly backup_path="${backup_dir}/${timestamp}"
readonly log_file="/var/log/backup.log"

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$log_file"
}

error_exit() {
  log "ERROR: $*"
  exit 1
}

# Check prerequisites
[[ -d "$source_dir" ]] || error_exit "Source directory $source_dir does not exist"
[[ -w "$backup_dir" ]] || error_exit "Backup directory $backup_dir is not writable"

# Perform backup
mkdir -p "$backup_path"
log "Starting backup of $source_dir to $backup_path"

if cp -r "$source_dir"/* "$backup_path/"; then
  log "Backup successful"
else
  error_exit "Backup failed"
fi

# Verify backup
if [[ $(find "$backup_path" -type f | wc -l) -gt 0 ]]; then
  log "Verification passed: files present in backup"
else
  error_exit "Verification failed: backup directory is empty"
fi
```

### Example 3: Log rotation (production)

```bash
#!/usr/bin/env bash
set -euo pipefail

readonly log_dir="/var/log/myapp"
readonly max_age_days=7
readonly max_size_mb=100
readonly archive_dir="/var/log/myapp/archive"

cleanup() {
  [[ -f "$lock_file" ]] && rm -f "$lock_file"
}

trap cleanup EXIT

readonly lock_file="/var/run/log-rotation.lock"

# Prevent concurrent runs
if [[ -f "$lock_file" ]]; then
  echo "Log rotation already running" >&2
  exit 1
fi
touch "$lock_file"

mkdir -p "$archive_dir"

# Find and rotate logs older than max_age_days
find "$log_dir" -maxdepth 1 -name "*.log" -type f -mtime "+${max_age_days}" -print0 |
  while IFS= read -rd '' logfile; do
    gzip "$logfile"
    mv "${logfile}.gz" "$archive_dir/"
    echo "Rotated $(basename "$logfile")"
  done

# Find and compress large logs
find "$log_dir" -maxdepth 1 -name "*.log" -type f -size "+${max_size_mb}M" -print0 |
  while IFS= read -rd '' logfile; do
    mv "$logfile" "${logfile}.$(date +%s)"
    gzip "${logfile}."*
    echo "Compressed $(basename "$logfile")"
  done

echo "Log rotation complete"
```

**Key techniques:**
- `find ... -print0 | while IFS= read -rd '' file` safely handles filenames with spaces/newlines
- `trap cleanup EXIT` ensures the lock file is always removed
- `readonly` prevents accidental modification of constants

---

## 6 · Practical Demonstration

### Variables and parameter expansion

```console
$ name="Alice"
$ echo "$name"
Alice
$ echo "${name}"
Alice
$ echo "${name:-default}"
Alice
$ echo "${nonexistent:-default}"
default
$ path="/home/alice/file.txt"
$ echo "${path##*/}"        # Remove everything up to last /
file.txt
$ echo "${path%%.*}"        # Remove everything from first .
/home/alice/file
$ echo "${#path}"           # Length
23
```

### Conditionals

```bash
#!/bin/bash

file="/etc/passwd"

# File tests
if [[ -f "$file" ]]; then
  echo "$file exists and is a regular file"
fi

if [[ -r "$file" ]]; then
  echo "$file is readable"
fi

if [[ ! -w "$file" ]]; then
  echo "$file is not writable"
fi

# String comparison
name="Alice"
if [[ "$name" == "Alice" ]]; then
  echo "Name is Alice"
fi

if [[ "$name" =~ ^A ]]; then
  echo "Name starts with A"
fi

# Arithmetic
count=5
if (( count > 3 )); then
  echo "count > 3"
fi

# Combining conditions
if [[ -f "$file" && -r "$file" ]]; then
  echo "$file is a readable regular file"
fi

# Case statement
case "$1" in
  start)
    echo "Starting..."
    ;;
  stop)
    echo "Stopping..."
    ;;
  *)
    echo "Unknown command: $1"
    exit 1
    ;;
esac
```

### Loops

```bash
#!/bin/bash

# Loop with C-style syntax (efficient, no subshell)
for (( i=1; i<=5; i++ )); do
  echo "Iteration $i"
done

# Loop over array
files=("file1.txt" "file2.txt" "file3.txt")
for file in "${files[@]}"; do
  echo "Processing $file"
done

# Loop with while
count=1
while (( count <= 5 )); do
  echo "Count: $count"
  (( count++ ))
done

# Loop with until (opposite of while)
count=1
until (( count > 5 )); do
  echo "Count: $count"
  (( count++ ))
done

# Loop over command output (safe, using process substitution)
while IFS= read -r line; do
  echo "Line: $line"
done < <(cat /etc/hosts)

# break and continue
for i in {1..10}; do
  if (( i == 3 )); then
    continue          # Skip this iteration
  fi
  if (( i == 7 )); then
    break             # Exit loop entirely
  fi
  echo "$i"
done
```

### Functions

```bash
#!/bin/bash

# Simple function
greet() {
  echo "Hello, $1"
}

greet "Alice"                  # Hello, Alice

# Function with local variables
add() {
  local a=$1
  local b=$2
  local result=$((a + b))
  echo "$result"
}

sum=$(add 3 5)
echo "Sum: $sum"               # Sum: 8

# Function with error handling
safe_read() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    echo "Error: $file not found" >&2
    return 1
  fi
  cat "$file"
  return 0
}

if safe_read "/etc/passwd"; then
  echo "Read succeeded"
else
  echo "Read failed with exit code $?"
fi

# Recursive function
factorial() {
  local n=$1
  if (( n <= 1 )); then
    echo 1
  else
    local m=$((n - 1))
    local submult=$(factorial "$m")
    echo $((n * submult))
  fi
}

echo "5! = $(factorial 5)"     # 5! = 120
```

### Arrays and associative arrays

```bash
#!/bin/bash

# Indexed array
fruits=("apple" "banana" "cherry")
echo "${fruits[0]}"                    # apple
echo "${fruits[@]}"                    # all elements
echo "${#fruits[@]}"                   # 3 (length)

# Append to array
fruits+=("date")

# Loop over array
for fruit in "${fruits[@]}"; do
  echo "$fruit"
done

# Associative array (like a dictionary)
declare -A person

person[name]="Alice"
person[age]=30
person[city]="London"

echo "${person[name]} is ${person[age]} years old"  # Alice is 30 years old

# Loop over associative array
for key in "${!person[@]}"; do
  echo "$key: ${person[$key]}"
done
```

### Input and output

```bash
#!/bin/bash

# Read from keyboard (interactive)
read -p "Enter your name: " name
echo "Hello, $name"

# Read from stdin (with newline preservation)
while IFS= read -r line; do
  echo "Got: $line"
done

# Read with timeout
read -t 5 -p "Quick, enter something: " response
if [[ -z "$response" ]]; then
  echo "You didn't respond in time"
fi

# Here-document (multi-line string)
cat << 'EOF'
This is a
multi-line
string
EOF

# Here-document with variable expansion
name="Alice"
cat << EOF
Hello, $name
Your home is $HOME
EOF

# Here-document with redirection
cat << EOF > /tmp/config.conf
[settings]
name=myapp
port=8080
EOF

# Command substitution
files=$(find /tmp -type f -name "*.log")
echo "$files"

# Process substitution (connect command output to a file descriptor)
diff <(ls /dir1) <(ls /dir2)         # Show differences between two directories
```

### Debugging with `set -x` and `bash -x`

```bash
#!/bin/bash
set -euo pipefail

# Debug the next commands
set -x
mkdir -p /tmp/mydir
cd /tmp/mydir
set +x     # Turn debugging off

echo "Now debugging is off"

# Or run the entire script with debugging:
# bash -x script.sh
```

Output when run:
```
+ mkdir -p /tmp/mydir
+ cd /tmp/mydir
Now debugging is off
```

---

## 7 · Comparison Tables

### Execution methods

| Method | Behavior | Use case |
|---|---|---|
| `bash script.sh` | Runs script in a new Bash process | Always works; script does not need `chmod +x` |
| `./script.sh` | Runs script using shebang interpreter; requires `chmod +x` | Production scripts, cron jobs |
| `source script.sh` or `. script.sh` | Runs script in *current* shell; functions and variables are available after | Sourcing utilities, setting environment |

### Quoting and expansion

| Code | Result | Reason |
|---|---|---|
| `echo $var` | Value of `var` (word-split if spaces) | Unquoted expansion |
| `echo "$var"` | Value of `var` (no word-split) | Quoted — preserves spaces |
| `echo '$var'` | Literal string `$var` | Single quotes prevent expansion |
| `echo "$(cmd)"` | Output of `cmd` | Command substitution in double quotes |
| `echo '$(cmd)'` | Literal string `$(cmd)` | Single quotes prevent substitution |

### Conditional operators

| Operator | Meaning | Example | Notes |
|---|---|---|---|
| `-f` | File exists and is regular | `[[ -f /etc/passwd ]]` | Use with files |
| `-d` | Path exists and is directory | `[[ -d /home ]]` | Use with directories |
| `-e` | Path exists (any type) | `[[ -e /dev/null ]]` | File, dir, device, symlink, etc. |
| `-r` | File is readable | `[[ -r ~/.ssh/id_ed25519 ]]` | Check permissions |
| `-w` | File is writable | `[[ -w /tmp ]]` | Check write access |
| `-x` | File is executable | `[[ -x /bin/bash ]]` | Check execute bit |
| `-z` | String is empty | `[[ -z "$var" ]]` | True if length is 0 |
| `-n` | String is not empty | `[[ -n "$var" ]]` | True if length > 0 |
| `=` or `==` | Strings are equal | `[[ "$a" == "$b" ]]` | Both work in `[[ ]]` |
| `!=` | Strings are not equal | `[[ "$a" != "$b" ]]` | Also `!= ` in `[ ]` |
| `-lt` | Arithmetic less-than | `(( a < b ))` or `[[ a -lt b ]]` | Requires numbers |
| `-gt` | Arithmetic greater-than | `(( a > b ))` or `[[ a -gt b ]]` | Requires numbers |
| `-eq` | Arithmetic equal | `[[ $a -eq $b ]]` | For integer comparison |
| `-ne` | Arithmetic not-equal | `[[ $a -ne $b ]]` | For integer comparison |
| `&&` | Logical AND | `[[ -f "$file" && -r "$file" ]]` | Both conditions must be true |
| `\|\|` | Logical OR | `[[ -z "$var" \|\| "$var" == "none" ]]` | At least one condition must be true |
| `!` | Logical NOT | `[[ ! -f "$file" ]]` | Inverts the condition |

### `[[ ]]` vs `[ ]` vs `(( ))`

| Construct | Use for | Features | Speed |
|---|---|---|---|
| `[[ ... ]]` | Strings, files, patterns (RECOMMENDED) | No word-splitting, regex `=~`, `-d`, `-f`, etc. | Faster than `[ ]` |
| `[ ... ]` | POSIX portable code | Works in `sh`; fewer features | Slower; more careful quoting needed |
| `(( ... ))` | Arithmetic only | `>`, `<`, `==` work naturally (no `-lt`); C-style | Fast |

---

## 8 · Memory Tricks

> [!MEMORY]
> **The four pillars of safe shell scripts.**
>
> 1. **`set -euo pipefail`** — stop on error, undefined, pipe failure
> 2. **Always quote:** `"$var"` not `$var`
> 3. **Never `ls` in a loop** — use `find` or `while read`
> 4. **Debug with `bash -x`** — see what actually runs

> [!MEMORY]
> **`$@` vs `$*` — "You are always you, they are always different."**
>
> - `"$@"` → each argument is a separate string (`"$1" "$2" "$3"`) — preserves your identity
> - `"$*"` → all arguments concatenated into one string — loses identity
>
> Use `"$@"` 99% of the time.

> [!MEMORY]
> **`[ ]` vs `[[ ]]` — Brackets on the right are more right.**
>
> `[[ ]]` is newer, more features, safer. Use `[[ ]]` unless you need POSIX `[ ]` portability.

> [!MEMORY]
> **The three types of quotes, by strictness:**
>
> 1. **Single `'...'`** — strictest; nothing expands
> 2. **Double `"..."`** — medium; `$var` and `$(cmd)` expand
> 3. **`$'...'`** — fancy; escape sequences like `\n` work

> [!MEMORY]
> **Exit codes: 0 = good, non-zero = bad.**
>
> Check with `if command; then ...` (true if exit code is 0) or `|| handle_error` (run if exit code is non-zero).

---

## 9 · Interview Corner

<details>
<summary><strong>Beginner</strong> — What is a shebang, and why does it matter?</summary>

The shebang (or hashbang) is the first line of a script, starting with `#!`, followed by the path to an interpreter. For example, `#!/bin/bash` tells the kernel to run the script with the Bash interpreter when you execute the script directly (e.g., `./script.sh`).

It matters because:

1. **Portability** — without a shebang, the system does not know which shell to use
2. **Clarity** — readers know immediately which language the script is in
3. **Execution** — it enables direct execution (if the file has execute permission) without explicitly typing `bash script.sh`

Use `#!/usr/bin/env bash` rather than `#!/bin/bash` for maximum portability, because `bash` might be installed at a different path on different systems.

</details>

<details>
<summary><strong>Beginner</strong> — What does `set -e` do, and when would you use it?</summary>

`set -e` enables "exit on error" mode. If any command exits with a non-zero status, the script immediately exits. Without it, the script keeps running even if a command fails, often silently causing data loss or incorrect behaviour.

You should use `set -e` in almost every production script. The only exception is if you intentionally want to catch and handle specific failures (e.g., `command || handle_error`).

Combine it with `set -u` (error on undefined variables) and `set -o pipefail` (fail if any command in a pipe fails) for the maximum safety line: `set -euo pipefail`.

</details>

<details>
<summary><strong>Beginner</strong> — Explain the difference between `$var`, `"$var"`, and `'$var'`.</summary>

- `$var` — expands to the value of `var`, but if the value contains spaces, it is word-split into multiple arguments
- `"$var"` — expands to the value of `var`, preserving spaces as one argument
- `'$var'` — does not expand; it is the literal string `$var`

Example:

```bash
name="Alice Smith"
cp $name /backup       # WRONG: splits into cp Alice Smith /backup (3 args)
cp "$name" /backup     # RIGHT: one argument "Alice Smith"
cp '$name' /backup     # WRONG: tries to copy a file literally named "$name"
```

Always quote variables: `"$var"`. You will rarely regret it, and it prevents most scripting bugs.

</details>

<details>
<summary><strong>Beginner</strong> — Why should you never use `ls` in a loop?</summary>

Because `ls` is meant for human-readable output, not for parsing. If a filename contains spaces or newlines, `ls` splits it, and the loop breaks.

Example:

```bash
# WRONG
for file in $(ls /data); do
  process "$file"
done

# If /data/file one.txt exists, ls outputs:
# file
# one.txt
# The loop processes "file" and "one.txt" separately, not "file one.txt"
```

Instead, use `find` with `-print0` and `read`:

```bash
find /data -type f -print0 | while IFS= read -rd '' file; do
  process "$file"
done
```

This handles any filename correctly — spaces, newlines, special characters.

</details>

<details>
<summary><strong>Intermediate</strong> — What is a subshell, and how does it affect variables?</summary>

A subshell is a child Bash process created whenever:
- You use a pipe: `command1 | command2`
- You use command substitution: `$(command)` or `` `command` ``
- You run a command in the background: `command &`
- You explicitly start one: `(command)`

Variables set in a subshell do not affect the parent shell. Example:

```bash
count=0
echo "line1" | while read line; do
  ((count++))
done
echo "$count"     # Still 0, not 1 (the increment happened in a subshell)
```

To avoid this, use process substitution instead of pipes:

```bash
count=0
while read line; do
  ((count++))
done < <(echo "line1")
echo "$count"     # Now 1 (no subshell)
```

</details>

<details>
<summary><strong>Intermediate</strong> — Explain parameter expansion. What does `${file##*/}` do?</summary>

Parameter expansion is syntax for accessing or transforming variables. The syntax `${var##pattern}` removes the longest match of `pattern` from the start of `var`.

For `${file##*/}`:
- `file` is a variable (e.g., `/home/alice/myfile.txt`)
- `##` means "remove the longest match"
- `*/` means "anything up to and including the last slash"
- Result: just the filename (`myfile.txt`)

Other common expansions:

| Expansion | Result |
|---|---|
| `${file%%.*}` | Filename without extension (remove from first `.` to end) |
| `${file%.*}` | Remove shortest match (e.g., `.txt`); shortest is one `.` |
| `${#file}` | Length of `$file` |
| `${file:0:5}` | First 5 characters (substring) |
| `${file:5}` | Everything after character 5 |
| `${file:-default}` | Value of `file`, or `default` if unset |

</details>

<details>
<summary><strong>Intermediate</strong> — When would you use `trap`, and what is a common use case?</summary>

`trap` is a handler for signals and special conditions. The most common use is `trap cleanup EXIT`, which ensures cleanup code runs no matter how the script exits (normally, on error, or via signal).

Example:

```bash
#!/bin/bash
set -euo pipefail

cleanup() {
  echo "Cleaning up..."
  rm -f /tmp/working_file
  [[ -f "$lock_file" ]] && rm -f "$lock_file"
}

trap cleanup EXIT

# Script code here
```

Other common traps:
- `trap 'echo Interrupted; exit' SIGINT` — handle Ctrl+C gracefully
- `trap 'echo Error at line $LINENO' ERR` — catch errors with line number

</details>

<details>
<summary><strong>Intermediate</strong> — What is the difference between `[[ ]]` and `[ ]`?</summary>

Both are conditionals, but `[[ ]]` is newer and safer:

| Feature | `[[ ]]` | `[ ]` |
|---|---|---|
| Word-splitting | No (safer) | Yes (need more quoting) |
| Regex matching `=~` | Yes | No |
| Logical `&&` and `\|\|` | Work as expected | Must use `-a` and `-o` |
| Performance | Faster (built-in) | Slower (external command) |
| Portability | Bash/Ksh only | POSIX (`sh` too) |

Use `[[ ]]` in Bash scripts. Use `[ ]` only if you need POSIX portability (running in `sh`).

</details>

<details>
<summary><strong>Intermediate</strong> — What is `set -u`, and what problem does it solve?</summary>

`set -u` (or `set -o nounset`) makes Bash error immediately if you reference an undefined variable. Without it, undefined variables silently expand to an empty string, often causing bugs.

Example:

```bash
set -u
count=$nonexistent      # Error: nonexistent: unbound variable
echo "$count"           # Never reached
```

This catches typos like `$HOMEE` (you meant `$HOME`) or forgetting to define a variable. Combine with `set -e` and `set -o pipefail` for safe production scripts:

```bash
set -euo pipefail
```

</details>

<details>
<summary><strong>Advanced</strong> — Explain the difference between `$*` and `$@`, and why it matters for function arguments.</summary>

Both expand to all positional arguments, but:

- `$*` → a single string: `"$1 $2 $3"` (joined by `IFS`)
- `"$@"` → separate strings: `"$1" "$2" "$3"`

This matters when you pass arguments to another function. Example:

```bash
outer() {
  inner "$@"              # Each arg passed separately (RIGHT)
}

inner_bad() {
  inner $*                # All args joined into one string (WRONG)
}
```

If the caller invokes `outer "arg one" "arg two"`, the function receives two arguments. Using `$*` would join them into one argument `"arg one arg two"`.

**Always use `"$@"` when passing arguments to another function.**

</details>

<details>
<summary><strong>Advanced</strong> — How does `bash -x` help you debug a script, and when would you use it?</summary>

`bash -x` runs a script with execution tracing enabled (`-x` is short for `xtrace`). Every command is printed to stderr before it runs, showing the exact command with all expansions and substitutions applied.

Example:

```bash
#!/bin/bash
# save as script.sh
name="Alice Smith"
cp "$name" /backup
```

Running:
```console
$ bash -x script.sh
+ name='Alice Smith'
+ cp 'Alice Smith' /backup
cp: cannot stat 'Alice Smith': No such file or directory
```

You see immediately that `name` contains a space, and the exact command that failed.

Use `bash -x` when:
- A script fails and you do not understand why
- A script produces unexpected output
- You are developing and need to verify expansions

Alternatively, add `set -x` inside the script to debug specific sections, and `set +x` to turn it off.

</details>

<details>
<summary><strong>Advanced</strong> — Design a robust script that deletes files older than 7 days, with a dry-run mode and proper error handling.</summary>

Here is a production-grade script:

```bash
#!/usr/bin/env bash
set -euo pipefail

readonly target_dir="/var/log/old"
readonly max_age_days=7
readonly log_file="/var/log/cleanup.log"

dry_run="${1:-false}"

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$log_file"
}

cleanup() {
  # Ensure lock file is removed
  [[ -f "$lock_file" ]] && rm -f "$lock_file"
}

trap cleanup EXIT

readonly lock_file="/var/run/cleanup-old-files.lock"

if [[ -f "$lock_file" ]]; then
  log "ERROR: Cleanup already running (lock file exists)"
  exit 1
fi
touch "$lock_file"

if [[ ! -d "$target_dir" ]]; then
  log "ERROR: Target directory $target_dir does not exist"
  exit 1
fi

log "Starting cleanup: target=$target_dir, max_age=${max_age_days}d, dry_run=$dry_run"

deleted_count=0
total_freed_bytes=0

# Use find to locate old files safely
find "$target_dir" -maxdepth 1 -type f -mtime "+${max_age_days}" -print0 |
  while IFS= read -rd '' file; do
    file_size=$(stat -c%s "$file" 2>/dev/null || echo 0)
    
    if [[ "$dry_run" == "true" ]]; then
      log "[DRY RUN] Would delete: $file ($(numfmt --to=iec $file_size 2>/dev/null || echo $file_size bytes))"
    else
      if rm -f "$file"; then
        log "Deleted: $file ($(numfmt --to=iec $file_size 2>/dev/null || echo $file_size bytes))"
        (( deleted_count++ )) || true
        (( total_freed_bytes += file_size )) || true
      else
        log "ERROR: Failed to delete $file"
      fi
    fi
  done

if [[ "$dry_run" != "true" ]]; then
  log "Cleanup complete: deleted=$deleted_count files, freed=$(numfmt --to=iec $total_freed_bytes 2>/dev/null || echo $total_freed_bytes bytes)"
else
  log "[DRY RUN] Complete (no files actually deleted)"
fi
```

Key production techniques:
1. **`set -euo pipefail`** — catch all errors
2. **Lock file** — prevent concurrent runs
3. **Dry-run mode** — test before destroying
4. **Logging** — timestamped to a file
5. **Proper cleanup** — `trap cleanup EXIT`
6. **Safe file handling** — `find ... -print0 | while IFS= read -rd '' file`
7. **Human-readable output** — `numfmt` for byte sizes

</details>

---

## 10 · Common Mistakes

> [!MISTAKE]
> **Not quoting variables.** `cp $file /backup` fails if `$file` contains spaces. Always write `cp "$file" /backup`. This is the #1 cause of production script failures.

> [!MISTAKE]
> **Forgetting `set -e`.** Without it, a command can fail silently and the script keeps running, corrupting data or deploying the wrong version. Every script should start with `set -euo pipefail`.

> [!MISTAKE]
> **Using `ls` in a loop.** `for file in $(ls /data)` breaks if filenames contain spaces or newlines. Use `find /data -type f -print0 | while IFS= read -rd '' file` instead.

> [!MISTAKE]
> **Setting variables in a subshell and expecting them to persist.** `count=0; echo line | while read l; do ((count++)); done; echo $count` prints 0, not 1, because the loop runs in a subshell. Use `while ... < <(cmd)` instead (process substitution, no subshell).

> [!DANGER]
> **Using `rm` without `-f` in a script.** If a file does not exist, `rm file` fails and stops the script (if `set -e` is on). Use `rm -f file` or `[[ -f file ]] && rm file` to be explicit.

> [!DANGER]
> **Running a script with untrusted input without validation.** If `$1` is used directly in a command like `rm -rf $1/*`, a malicious user can pass `/ *` and delete the entire filesystem. Always validate and quote: `rm -rf "${safe_dir:?}"/*`.

> [!MISTAKE]
> **Mixing `&&` and `||` without parentheses.** `command1 || command2 && command3` is unclear. Use `(command1 || command2) && command3` to clarify precedence.

> [!MISTAKE]
> **Not using `local` in functions.** Variables defined in a function are global by default, polluting the namespace. Use `local var=value` to keep them scoped.

> [!PROD]
> **Not logging in production scripts.** A backup script that completes silently gives no confidence. Always log: `echo "Backup: $file" | tee -a "$log_file"`. When a 3 a.m. page arrives, logs are your first clue.

> [!PROD]
> **Hardcoding paths and values.** Use variables: `readonly backup_dir="/backup"`. When the path changes, you edit one line, not ten. Use `readonly` for constants to prevent accidental modification.

---

## 11 · Summary & Mind Map

Bash scripting is the glue that holds Linux systems together. The core idea is simple: a text file containing commands, run line by line, with the ability to branch (conditionals), repeat (loops), and reuse (functions). The challenge is not the syntax — it is discipline.

The four pillars of safe scripts separate working code from production code:

1. **`set -euo pipefail`** — stop on error, undefined variables, and pipe failures
2. **Always quote variables** — `"$var"` not `$var`
3. **Avoid `ls` in loops** — use `find` or `while read`
4. **Debug with `bash -x`** — see the actual commands

Internalize these four, and you will write scripts that do not destroy production systems at 3 a.m.

```mermaid
mindmap
  root(("Bash Scripting"))
    Fundamentals
      Shebang & execution
      Variables & expansion
      Quoting (single/double/$'')
      Exit codes & $?
    Control Flow
      if/[[ ]]/case
      Loops (for/while/until)
      break/continue
      trap for cleanup
    Data Structures
      Indexed arrays
      Associative arrays
      ${#arr[@]}
    Functions
      Parameters ($1 $@ $#)
      local variables
      Recursion
      return codes
    I/O
      read, read -r
      Redirects (>/>>/</<< EOF)
      Here-documents
      Command substitution
    Safety (4 pillars)
      set -e (errexit)
      set -u (nounset)
      set -o pipefail
      Always quote "$var"
    Debugging
      bash -x execution trace
      set -x / set +x
      trap ERR
      PS4 for debug prefix
    Real-world
      File operations safely
      Logging & timestamps
      Lock files
      Error handling with || exit
```

---

## 12 · Cheat Sheet

```diagram title="Bash Scripting at a glance"
┌─────────────────────────────────────────────────────────────────┐
│ SCRIPT SKELETON                                                 │
├─────────────────────────────────────────────────────────────────┤
│ #!/usr/bin/env bash                                             │
│ set -euo pipefail                                               │
│                                                                 │
│ readonly VAR="value"                                            │
│                                                                 │
│ log() { echo "[$(date +'%T')] $*"; }                           │
│ cleanup() { rm -f /tmp/lock; }                                 │
│ trap cleanup EXIT                                              │
│                                                                 │
│ [[ -f "$config" ]] || { log "Missing $config"; exit 1; }      │
│ ... rest of script                                              │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ VARIABLES & EXPANSION                                           │
├─────────────────────────────────────────────────────────────────┤
│ var="value"           # Assignment (no spaces around =)         │
│ echo "$var"           # Expansion (ALWAYS quote)                │
│ echo "${var}"         # Same, more explicit                     │
│ echo "${var:-default}"# Use default if unset                    │
│ echo "${var:?error}"  # Error if unset                          │
│ echo "${var##path/*}" # Remove longest match from start         │
│ echo "${#var}"        # Length of var                           │
│ $0=$script, $1=$arg1, $@=all_args, $?=exit_code                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ CONDITIONALS                                                    │
├─────────────────────────────────────────────────────────────────┤
│ if [[ -f "$file" ]]; then ... fi                               │
│ if [[ -d "$dir" ]]; then ... fi                                │
│ if [[ -z "$var" ]]; then ... fi                  # empty string │
│ if [[ "$a" == "$b" ]]; then ... fi                             │
│ if [[ "$a" =~ ^pattern ]]; then ... fi                         │
│ if (( count > 5 )); then ... fi                  # arithmetic  │
│ [[ -f "$f" && -r "$f" ]] && echo "readable"      # AND         │
│ [[ -z "$x" || "$x" == "none" ]] && echo "empty"  # OR          │
│ case "$opt" in start) ... ;; stop) ... ;; esac                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ LOOPS                                                           │
├─────────────────────────────────────────────────────────────────┤
│ for (( i=1; i<=10; i++ )); do echo $i; done                    │
│ for item in "${array[@]}"; do echo "$item"; done               │
│ while read -r line; do echo "$line"; done < file               │
│ find /dir -name "*.log" -print0 |                              │
│   while IFS= read -rd '' f; do process "$f"; done              │
│ for i in {1..5}; do echo $i; done                              │
│ break                 # Exit loop                               │
│ continue              # Skip to next iteration                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ FUNCTIONS & ARRAYS                                              │
├─────────────────────────────────────────────────────────────────┤
│ func() { local x=$1; return 0; }                                │
│ func "$arg"           # Call with quoted argument               │
│ arr=("a" "b" "c")     # Indexed array                           │
│ echo "${arr[0]}"      # First element                           │
│ echo "${arr[@]}"      # All elements                            │
│ echo "${#arr[@]}"     # Length                                  │
│ declare -A map; map[key]=value   # Associative array            │
│ for k in "${!map[@]}"; do echo "$k: ${map[$k]}"; done           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ SAFETY: THE FOUR PILLARS                                        │
├─────────────────────────────────────────────────────────────────┤
│ set -e              # Exit if any command fails                 │
│ set -u              # Error if undefined variable used          │
│ set -o pipefail     # Fail if any command in pipe fails        │
│ set -x              # Print each command before running         │
│                                                                 │
│ Combine: set -euo pipefail                                      │
│                                                                 │
│ "$var"              # ALWAYS quote variables                    │
│ find ... -print0 | while read -rd '' f  # Safe filenames        │
│ bash -x script.sh   # Debug: see actual commands                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ I/O & REDIRECTION                                               │
├─────────────────────────────────────────────────────────────────┤
│ read -p "Prompt: " var        # Read from stdin                 │
│ read -r line < file           # Read line from file (preserve \)│
│ echo "output" > file          # Redirect to file (overwrite)   │
│ echo "output" >> file         # Append to file                  │
│ cmd1 | cmd2                   # Pipe stdout of cmd1 to cmd2     │
│ cmd 2> errors.log             # Redirect stderr                 │
│ cmd > output.log 2>&1         # Both stdout and stderr          │
│ cat << EOF                    # Here-document                   │
│ multi-line                                                      │
│ text                                                            │
│ EOF                                                             │
│ $(command)                    # Command substitution            │
│ <(command)                    # Process substitution            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ DEBUGGING                                                       │
├─────────────────────────────────────────────────────────────────┤
│ bash -x script.sh             # Run with trace on               │
│ set -x; commands; set +x      # Enable/disable trace locally   │
│ PS4='+ ${BASH_SOURCE}:${LINENO}: '  # Better trace prefix       │
│ trap 'echo Error at $LINENO' ERR    # Catch errors              │
│ echo "${BASH_REMATCH[@]}"     # After =~ match, debug regex    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 13 · Practice

### Flashcard Questions

| Question | Answer |
|---|---|
| What does `set -e` do? | Exits the script if any command fails (non-zero exit) |
| When should you quote a variable? | Always — `"$var"` is the default, unquoted is rare |
| What is the difference between `$@` and `$*`? | `"$@"` is separate strings; `$*` is one concatenated string |
| Why is `for f in $(ls)` bad? | Filenames with spaces or newlines break; use `find` with `-print0` instead |
| What does `trap cleanup EXIT` do? | Ensures `cleanup()` runs when the script exits, for any reason |
| What is the exit code of the last command? | Stored in `$?`; 0 is success, non-zero is failure |
| What does `set -u` do? | Errors if you reference an undefined variable |
| How do you call a function with arguments? | `func "arg1" "arg2"` (quote all arguments) |
| What is a subshell? | A child Bash process created by pipes, `$()`, or `(...)` |
| How do you permanently redirect stderr to a file? | `command 2> error.log` or `command 2>> error.log` for append |

### Fill-in-the-blank

1. **Every production script should start with:** `set ________` (answer: `-euo pipefail`)
2. **To read a filename safely from `find` output, use:** `find ... -print0 | while _______ read -rd '' file` (answer: `IFS= `)
3. **In a function, make variables local with the:** `______` keyword (answer: `local`)
4. **Parameter expansion to remove the longest path prefix:** `${file##______}` (answer: `*/`)
5. **To get the exit code of the last command:** Use the variable `$_` or `$?` (answer: `$?`)
6. **When you want a command to fail silently if it does not exist, append:** `___ exit` (answer: `|| true`)

### True/False

1. **T / F** — In a Bash script, `[ ]` and `[[ ]]` are identical. **False** — `[[ ]]` is newer, safer, and handles word-splitting better.
2. **T / F** — The exit code 0 means the command failed. **False** — 0 means success; non-zero means failure.
3. **T / F** — You can use `$*` instead of `"$@"` when passing arguments to a function. **False** — `"$@"` preserves argument boundaries; `$*` concatenates them.
4. **T / F** — Using `set -e` guarantees the script will not fail silently. **True** — The script exits immediately on any non-zero exit code.
5. **T / F** — A shebang is just a comment. **False** — It is metadata that tells the kernel which interpreter to use.
6. **T / F** — Variables set in a pipe command are available after the pipe. **False** — The pipe runs in a subshell; variables set there are lost.

### Lab: Write a script that deletes files older than 7 days

**Task:** Write a script called `cleanup.sh` that:
- Deletes files in `/var/log` older than 7 days
- Supports a `--dry-run` flag (show what would be deleted without deleting)
- Logs each action with a timestamp
- Handles errors gracefully (file does not exist, permission denied)
- Prevents concurrent runs with a lock file

**Example invocations:**
```console
$ ./cleanup.sh --dry-run    # Show what would be deleted
$ ./cleanup.sh              # Actually delete
```

**Hints:**
1. Use `find` with `-mtime +7` to find files older than 7 days
2. Parse `--dry-run` from `$1`
3. Create `/var/run/cleanup.lock` to prevent concurrent runs
4. Log output to `/var/log/cleanup.log` with timestamps
5. Use `trap cleanup EXIT` to remove the lock file
6. Check permissions before deleting: `[[ -w "$dir" ]]`

<details>
<summary>Answers</summary>

Here is a production-grade solution:

```bash
#!/usr/bin/env bash
set -euo pipefail

readonly target_dir="/var/log"
readonly max_age_days=7
readonly log_file="/var/log/cleanup.log"
readonly lock_file="/var/run/cleanup.lock"

dry_run=false
if [[ "${1:-}" == "--dry-run" ]]; then
  dry_run=true
fi

log() {
  local msg="$1"
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $msg" | tee -a "$log_file"
}

cleanup() {
  if [[ -f "$lock_file" ]]; then
    rm -f "$lock_file"
    log "Lock file removed"
  fi
}

trap cleanup EXIT

# Prevent concurrent runs
if [[ -f "$lock_file" ]]; then
  log "ERROR: cleanup already running (lock file exists)"
  exit 1
fi

touch "$lock_file"

# Verify target directory exists and is writable
if [[ ! -d "$target_dir" ]]; then
  log "ERROR: target directory $target_dir does not exist"
  exit 1
fi

if [[ ! -w "$target_dir" ]]; then
  log "ERROR: target directory $target_dir is not writable"
  exit 1
fi

log "Starting cleanup: dry_run=$dry_run, target=$target_dir, age>${max_age_days}d"

deleted_count=0
error_count=0

# Find and delete old files
find "$target_dir" -maxdepth 1 -type f -mtime "+${max_age_days}" -print0 2>/dev/null |
  while IFS= read -rd '' file; do
    if [[ $dry_run == "true" ]]; then
      log "[DRY RUN] Would delete: $file"
    else
      if rm -f "$file" 2>/dev/null; then
        log "Deleted: $file"
        (( deleted_count++ )) || true
      else
        log "ERROR: Failed to delete $file"
        (( error_count++ )) || true
      fi
    fi
  done

if [[ $dry_run == "true" ]]; then
  log "Dry run complete (no files deleted)"
else
  log "Cleanup complete: deleted=$deleted_count, errors=$error_count"
fi
```

**Key points:**
- `set -euo pipefail` at the start
- `readonly` for constants
- `trap cleanup EXIT` ensures lock is removed
- `find -mtime +7` finds files older than 7 days
- `-print0` and `read -rd ''` handle filenames safely
- `--dry-run` flag for testing before destructive operation
- Logging to file and stdout simultaneously with `tee -a`

</details>

### PDF Challenge Questions

The source PDF includes the following challenges (all preserved here):

**Challenge 1:** Write a script that reads a list of usernames from a file and creates a home directory for each if it does not already exist.

**Challenge 2:** Write a script that monitors a directory and alerts (via email or log) if a file is modified.

**Challenge 3:** Write a deployment script that pulls the latest code, runs tests, and rolls back if tests fail.

**Challenge 4:** Write a script that backs up all `.conf` files in `/etc` to a timestamped directory, compresses it, and uploads it to an S3 bucket.

**Challenge 5:** Write a system health check script that reports CPU, memory, disk usage, and service status; exit with a non-zero code if any metric is critical.

<details>
<summary>Answers</summary>

**Challenge 1: Create home directories**

```bash
#!/usr/bin/env bash
set -euo pipefail

user_file="$1"
base_dir="/home"

[[ -f "$user_file" ]] || { echo "File not found: $user_file"; exit 1; }

while IFS= read -r username; do
  [[ -z "$username" ]] && continue       # Skip empty lines
  user_home="${base_dir}/${username}"
  
  if [[ -d "$user_home" ]]; then
    echo "Directory already exists: $user_home"
  else
    mkdir -p "$user_home"
    echo "Created: $user_home"
  fi
done < "$user_file"
```

**Challenge 2: Monitor directory for changes**

```bash
#!/usr/bin/env bash
set -euo pipefail

target_dir="${1:-.}"
log_file="/var/log/monitor.log"

# Baseline hash of directory contents
initial_state=$(find "$target_dir" -type f -exec md5sum {} \; | sort)

while true; do
  sleep 5
  current_state=$(find "$target_dir" -type f -exec md5sum {} \; | sort)
  
  if [[ "$initial_state" != "$current_state" ]]; then
    echo "[$(date +'%T')] Directory modified: $target_dir" >> "$log_file"
    initial_state="$current_state"
  fi
done
```

**Challenge 3: Deployment with rollback**

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_dir="/app"
backup_dir="/backups"
timestamp=$(date +%s)
backup_path="${backup_dir}/app_${timestamp}"

log() { echo "[$(date +'%T')] $*"; }

trap 'log "Deployment failed"; exit 1' ERR

log "Creating backup..."
mkdir -p "$backup_dir"
cp -r "$repo_dir" "$backup_path"

log "Pulling latest code..."
cd "$repo_dir"
git pull origin main

log "Running tests..."
if ! npm test; then
  log "Tests failed. Rolling back..."
  rm -rf "$repo_dir"
  mv "$backup_path" "$repo_dir"
  exit 1
fi

log "Deployment successful"
rm -rf "$backup_path"  # Clean up backup on success
```

**Challenge 4: Backup and upload to S3**

```bash
#!/usr/bin/env bash
set -euo pipefail

backup_dir="/tmp/etc_backup_$(date +%s)"
s3_bucket="s3://my-backups"

mkdir -p "$backup_dir"
find /etc -name "*.conf" -type f -exec cp {} "$backup_dir/" \;

tar -czf "${backup_dir}.tar.gz" -C /tmp "$(basename "$backup_dir")"
aws s3 cp "${backup_dir}.tar.gz" "$s3_bucket/"

rm -rf "$backup_dir" "${backup_dir}.tar.gz"
echo "Backup uploaded to $s3_bucket"
```

**Challenge 5: System health check**

```bash
#!/usr/bin/env bash
set -euo pipefail

cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print int($2)}')
mem_usage=$(free | grep Mem | awk '{print int($3/$2*100)}')
disk_usage=$(df / | tail -1 | awk '{print int($5)}')

critical=0

[[ $cpu_usage -gt 80 ]] && { echo "CRITICAL: CPU at $cpu_usage%"; critical=1; }
[[ $mem_usage -gt 85 ]] && { echo "CRITICAL: Memory at $mem_usage%"; critical=1; }
[[ $disk_usage -gt 90 ]] && { echo "CRITICAL: Disk at $disk_usage%"; critical=1; }

if systemctl is-active --quiet nginx; then
  echo "OK: nginx running"
else
  echo "CRITICAL: nginx not running"
  critical=1
fi

exit $critical
```

</details>

---

> [!NOTE]
> **Next chapter — Chapter 18: sed and awk.** Now that you can write scripts, learn the two text-processing powerhouses that make scripts fast and powerful. Pipes meet patterns; 1970s UNIX wizardry meets 2026.

