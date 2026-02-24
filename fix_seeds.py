import os
import re

def fix_file(filepath, deck_dir):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Strip "**Requirements**:\n"
    content = content.replace('"**Requirements**:\\n', '"')

    # Fix image keys
    # Matches: "title": "Some Title", ... "image": "some_wrong_image.png",
    # We can just write a quick script to find "title" and replace the subsequent "image"
    
    # Actually, the simplest way is to evaluate the list, modify it, and write it back
    pass

def simple_fix():
    for filename in ['backend/seed_cards.py', 'backend/seed_research_cards.py', 'backend/config.py']:
        if not os.path.exists(filename):
            continue
            
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        out_lines = []
        current_title = None
        for line in lines:
            if '"title":' in line:
                # extract title
                m = re.search(r'"title":\s*"([^"]+)"', line)
                if m:
                    current_title = m.group(1)
            elif '"requirements":' in line:
                line = line.replace('**Requirements**:\\n', '')
            elif '"image":' in line and current_title:
                expected_img = current_title.lower().replace(" ", "_").replace("'", "") + ".png"
                line = re.sub(r'"image":\s*"[^"]+"', f'"image": "{expected_img}"', line)
            
            out_lines.append(line)
            
        with open(filename, 'w', encoding='utf-8') as f:
            f.writelines(out_lines)

if __name__ == '__main__':
    simple_fix()
    print("Fixed text formats and images!")
