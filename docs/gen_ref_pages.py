from pathlib import Path

import mkdocs_gen_files

src = Path(__file__).parent.parent / "src" / "app"
nav = mkdocs_gen_files.Nav()  # type: ignore[attr-defined, no-untyped-call]

for path in sorted(src.rglob("*.py")):
    if path.name == "__init__.py" or path.name.startswith("_"):
        continue

    module_path = path.relative_to(src.parent).with_suffix("")
    doc_path = module_path.with_suffix(".md")
    full_doc_path = Path("reference") / doc_path

    parts = tuple(module_path.parts)
    nav[parts] = str(doc_path)

    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        fd.write(f"# `{'.'.join(parts)}`\n\n")
        fd.write(f"::: {'.'.join(parts)}\n")

    mkdocs_gen_files.set_edit_path(full_doc_path, path)

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.write("* [Overview](index.md)\n")
    nav_file.writelines(nav.build_literate_nav())
