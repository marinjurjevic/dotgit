import logging
import os
import re

import dotgit.info as info


class Filelist:
    def __init__(self, fname):
        self.groups = {}
        self.files = {}

        logging.debug(f'parsing filelist in {fname}')

        with open(fname, 'r') as f:
            for line in f.readlines():
                line = line.strip()

                if not line or line.startswith('#'):
                    continue

                # group
                if '=' in line:
                    group, categories = line.split('=')
                    categories = categories.split(',')
                    if group == info.hostname:
                        categories.append(info.hostname)
                    self.groups[group] = categories
                # file
                else:
                    split = re.split('[:|]', line)

                    path, categories, plugin = split[0], ['common'], 'plain'
                    if len(split) >= 2:
                        if ':' in line:
                            categories = split[1].split(',')
                        else:
                            plugin = split[1]
                    if len(split) >= 3:
                        plugin = split[2]

                    if path not in self.files:
                        self.files[path] = []
                    self.files[path].append({
                        'categories': categories,
                        'plugin': plugin
                    })

    def activate(self, categories):
        # expand groups
        categories = [self.groups.get(c, [c]) for c in categories]
        # flatten category list
        categories = [c for cat in categories for c in cat]

        # later categories take precedence over earlier ones
        cat_priority = {c: i for i, c in enumerate(categories)}

        files = {}
        file_priority = {}
        for path in self.files:
            for group in self.files[path]:
                cat_list = group['categories']
                matching = set(categories) & set(cat_list)
                if matching:
                    priority = max(cat_priority[c] for c in matching)
                    if path not in files:
                        files[path] = group
                        file_priority[path] = priority
                    elif priority > file_priority[path]:
                        files[path] = group
                        file_priority[path] = priority
                    elif priority == file_priority[path]:
                        logging.error('multiple category lists active for '
                                      f'{path}: {files[path]["categories"]} '
                                      f'and {cat_list}')
                        raise RuntimeError

        return files

    # generates a list of all the filenames in each plugin for later use when
    # cleaning the repo
    def manifest(self):
        manifest = {}

        for path in self.files:
            for instance in self.files[path]:
                plugin = instance['plugin']
                for category in instance['categories']:
                    if category in self.groups:
                        categories = self.groups[category]
                    else:
                        categories = [category]

                    if plugin not in manifest:
                        manifest[plugin] = []

                    for category in categories:
                        manifest[plugin].append(os.path.join(category, path))

        return manifest
