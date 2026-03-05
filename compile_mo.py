#!/usr/bin/env python3
"""Compile .po files to .mo files."""
import os
import sys

def compile_po(po_path, mo_path):
    try:
        from babel.messages.pofile import read_po
        from babel.messages.mofile import write_mo
        with open(po_path, 'rb') as f:
            catalog = read_po(f)
        with open(mo_path, 'wb') as f:
            write_mo(f, catalog)
        return True, None
    except Exception as e:
        return False, str(e)

base = os.path.dirname(os.path.abspath(__file__))
locales = os.path.join(base, 'locales')

results = []
for lang in ['id', 'en']:
    lc_dir = os.path.join(locales, lang, 'LC_MESSAGES')
    po = os.path.join(lc_dir, 'messages.po')
    mo = os.path.join(lc_dir, 'messages.mo')
    if os.path.exists(po):
        ok, err = compile_po(po, mo)
        results.append(f"{'OK' if ok else 'FAIL'}: {lang} -> {mo}" + (f" ({err})" if err else ""))
    else:
        results.append(f"SKIP: {lang} (no .po file at {po})")

# Write results to a file so we can read them
out_path = os.path.join(base, 'compile_result.txt')
with open(out_path, 'w') as f:
    f.write('\n'.join(results) + '\n')
