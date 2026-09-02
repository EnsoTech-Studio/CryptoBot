import glob
import os
import re

def verify():
    errors = []
    total_images = 0
    base_dir = os.path.dirname(os.path.abspath(__file__))
    md_files = glob.glob(os.path.join(base_dir, '**', '*.md'), recursive=True)
    
    print(f"Found {len(md_files)} markdown files to check.")
    for md in md_files:
        with open(md, 'r', encoding='utf-8') as f:
            content = f.read()
        imgs = re.findall(r'!\[.*?\]\((.*?)\)', content)
        for img in imgs:
            total_images += 1
            # Resolve relative path from the markdown file's directory
            resolved_path = os.path.normpath(os.path.join(os.path.dirname(md), img))
            if not os.path.exists(resolved_path):
                errors.append(f"Missing image: '{img}' in {os.path.relpath(md, base_dir)} -> {resolved_path}")
            else:
                print(f"  [OK] {os.path.basename(resolved_path)} (from {os.path.relpath(md, base_dir)})")

    if errors:
        print("\nERRORS DETECTED:")
        for err in errors:
            print("  - " + err)
        return False
    else:
        print(f"\nSUCCESS: All {total_images} diagram image references exist and are valid!")
        return True

if __name__ == '__main__':
    ok = verify()
    if not ok:
        exit(1)
