import os

# ================= CONFIG =================
PROJECT_ROOT = "."
OUTPUT_FILE = "PROJECT_DUMP.txt"

IGNORE_DIRS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
    "node_modules",
    ".txt",
    ".md",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".toml",
}

# ✅ Added ignore files list
IGNORE_FILES = {
    OUTPUT_FILE,
    "dump_project.py",  # exclude this script
}

EXCLUDE_EXTENSIONS = {
    ".json",  # explicitly exclude JSON
}

INCLUDE_EXTENSIONS = {
    ".py",
    ".html",
}

MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB
# ==========================================


def should_skip_dir(dirname):
    return dirname in IGNORE_DIRS


def should_include_file(filename):
    ext = os.path.splitext(filename)[1].lower()

    if ext in EXCLUDE_EXTENSIONS:
        return False

    if INCLUDE_EXTENSIONS:
        return ext in INCLUDE_EXTENSIONS

    return True


def is_separator_line(line):
    stripped = line.strip()

    if not stripped:
        return False

    # lines made only of repeating symbols
    chars = set(stripped)
    if len(chars) == 1 and list(chars)[0] in {"=", "-", "#", "*"}:
        return True

    return False


def clean_code(content):
    lines = content.splitlines()

    cleaned = []
    for line in lines:
        if is_separator_line(line):
            continue
        cleaned.append(line)

    return "\n".join(cleaned)


def get_file_size_safe(path):
    try:
        return os.path.getsize(path)
    except:
        return 0


def write_header(out, title):
    out.write("\n" + "=" * 80 + "\n")
    out.write(f"{title}\n")
    out.write("=" * 80 + "\n\n")


def main():

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:

        write_header(out, f"[PROJECT ROOT] {os.path.abspath(PROJECT_ROOT)}")

        for root, dirs, files in os.walk(PROJECT_ROOT):

            dirs[:] = [d for d in dirs if not should_skip_dir(d)]

            for file in files:

                # ✅ Skip ignored files
                if file in IGNORE_FILES:
                    continue

                if not should_include_file(file):
                    continue

                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, PROJECT_ROOT)

                size = get_file_size_safe(full_path)

                if size > MAX_FILE_SIZE:
                    out.write(f"\n[FILE] {relative_path}\n")
                    out.write("[SKIPPED: TOO LARGE]\n\n")
                    continue

                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        content = clean_code(content)
                except Exception as e:
                    content = f"[ERROR READING FILE: {e}]"

                out.write(f"\n[FILE] {relative_path}\n\n")
                out.write(content)
                out.write("\n")

    print(f"\n✅ Dump created: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()