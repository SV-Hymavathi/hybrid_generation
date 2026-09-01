# Running the USR→English tool on Windows (VS Code + WSL)

These are the exact steps and commands that get the tool running. The tool needs
Linux command-line programs (Apertium), so on Windows you run it **inside WSL**,
not in PowerShell/CMD.

---

## 0. One-time: install WSL (Ubuntu)

Open **PowerShell as Administrator** and run:

```powershell
wsl --install -d Ubuntu
```

Reboot if it asks you to. After reboot, Ubuntu opens and asks you to create a
UNIX username and password. Do that, then close it.

(If `wsl --install` says WSL is already installed, just run `wsl` to open it.)

---

## 1. One-time: VS Code + WSL extension

1. Install **VS Code** on Windows (normal Windows installer).
2. In VS Code, install the extension **"WSL"** (publisher: Microsoft).
3. Open the WSL window: press `Ctrl+Shift+P` → type **"WSL: Connect to WSL"** →
   Enter. The bottom-left green corner should say **"WSL: Ubuntu"**.

From now on, the VS Code terminal (`` Ctrl+` ``) is an **Ubuntu/WSL** terminal.
Run every command below in that terminal.

---

## 2. Put the project inside WSL

Keep the project on the Linux filesystem (`~`), NOT under `/mnt/c/...` — it runs
much faster and avoids permission issues.

In the WSL terminal:

```bash
cd ~
mkdir -p projects && cd projects
```

Then copy the unzipped `multilingual_rule_based_updated` folder here. Easiest way:
in VS Code (connected to WSL) use **File → Open Folder** and pick
`~/projects`, then drag the folder in; or from Windows copy the zip into
`\\wsl$\Ubuntu\home\<your-user>\projects\` and unzip it in WSL:

```bash
sudo apt-get update && sudo apt-get install -y unzip
unzip multilingual_rule_based_updated.zip
cd multilingual_rule_based_updated
```

---

## 3. One-time: install system dependencies (Apertium toolchain)

This is the part that does NOT exist on a plain Python install and is the usual
reason the tool "doesn't work".

```bash
sudo apt-get update
sudo apt-get install -y apertium lttoolbox python3 python3-pip python3-venv
```

Verify the Apertium tools are on the PATH (all three must print a path):

```bash
which lt-proc apertium-destxt apertium-retxt
```

---

## 4. One-time: install Python dependencies

Use a virtual environment so it stays clean:

```bash
cd ~/projects/multilingual_rule_based_updated
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install wxconv indic_transliteration pandas requests groq
```

Notes:
- `groq` is optional (only used by the LLM `[mask]` filler). The tool runs
  without it, but installing it avoids an import warning.
- If `pip install wxconv` is slow, that is normal the first time.

---

## 5. (Optional) the Groq API key

The hardcoded key was removed. The tool reads it from an environment variable
only. You only need this if you use the LLM mask-filler; normal generation does
NOT need it. If you do need it:

```bash
export GROQ_API_KEY="your-own-new-key"
```

---

## 6. Provide input and run

The tool reads its input from `gen_input.txt` in the project root. Put one or
more USRs there, each block as `<sent_id=...> ... </sent_id>`, separated by blank
lines. A 30-sentence sample already ships in `gen_input.txt`.

Run (the venv must be active — step 4):

```bash
cd ~/projects/multilingual_rule_based_updated
source .venv/bin/activate          # if not already active
python3 hindi_gen.py --lang en
```

The final result is printed on the log line that starts with:

```
log : [OK]:hindi_generation output : {'Tourism_001': ['[one line]_SUBJ ...']}
```

That dictionary `{sent_id: [chunked_output]}` is the generated chunks.

---

## 7. Everyday use (after the one-time setup)

```bash
cd ~/projects/multilingual_rule_based_updated
source .venv/bin/activate
# edit gen_input.txt with your USRs, then:
python3 hindi_gen.py --lang en
```

---

## Troubleshooting

- **`ModuleNotFoundError: No module named 'wxconv'` (or indic_transliteration,
  groq):** the venv isn't active, or pip step was skipped. Run
  `source .venv/bin/activate` then re-run the `pip install ...` line.
- **`/bin/sh: 1: lt-proc: not found` / `apertium-destxt: not found`:** Apertium
  isn't installed. Re-run step 3 (`sudo apt-get install -y apertium lttoolbox`)
  and check `which lt-proc`.
- **Output words look like raw WX (e.g. `gaDa`, `steSana`) with `#`:** you are
  reading the intermediate debug line `chunked_data = {...}`. The FINAL output
  is the later line `hindi_generation output : {...}` — use that one.
- **`--lang hi` gives empty output:** expected. The tool currently generates
  **English only**; the Hindi path is not wired end-to-end. See
  `CHANGES_AND_REMAINING_RULES.md`.
- **Everything crashes with `KeyError: 'cat'`:** you are on an old copy. This
  build has the fix; make sure you unzipped the updated zip.

---

## What this build generates

English chunked output from Hindi (Devanagari/WX) USR. See:
- `CHANGES_AND_REMAINING_RULES.md` — what was fixed, what rules remain, and the
  honest status of multilingual support.
- `DIFF_REPORT_32_TARGETS.md` — tool-vs-gold differences and their status.
