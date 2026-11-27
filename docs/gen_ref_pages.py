from pathlib import Path

import mkdocs_gen_files
from mkdocs_gen_files.nav import Nav

src = Path(__file__).parent.parent / "src" / "app"
nav = Nav()  # type: ignore[no-untyped-call]  # Nav.__init__ has no annotations.

for path in sorted(src.rglob("*.py")):
    if path.name == "__init__.py" or any(
        part.startswith("_") for part in path.relative_to(src).parts
    ):
        continue

    module_path = path.relative_to(src.parent).with_suffix("")
    doc_path = module_path.with_suffix(".md")
    full_doc_path = Path("reference") / doc_path

    parts = tuple(module_path.parts)
    nav[parts] = str(doc_path)

    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        fd.write(f"# `{'.'.join(parts)}`\n\n")
        fd.write(f"::: {'.'.join(parts)}\n")

    # Edit paths are relative to docs/.
    mkdocs_gen_files.set_edit_path(
        full_doc_path,
        Path("..", "src") / module_path.with_suffix(".py"),
    )

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.write("* [Overview](index.md)\n")
    nav_file.writelines(nav.build_literate_nav())
