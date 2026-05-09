import os
import json

folder_path = './dataset'
folders = []
for roots, dirs, files in os.walk(folder_path):
    for file in files:
        if 'type.raw' in file:
            folders.append(roots)
#folders = [os.path.join(folder_path, name) for name in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, name))]

# Generate a json list
json_list = json.dumps(folders, indent=4, ensure_ascii=False)

# Output the json list with each element separated by a newline
print(json_list.replace('",\n    "', '",\n    "'))

