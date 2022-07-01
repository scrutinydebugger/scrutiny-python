import os
from glob import glob
import re
import json
import sys
from datetime import datetime
import math
import argparse

global base_folder
base_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def get_files(folders, language = None):
    global base_folder

    if language == 'cpp':
        extensions = ['*.cpp', '*.h', '*.c']  
        exclude_patterns = []
    elif language == 'python':
        exclude_patterns = [r'__init__\.py$']
        extensions = ['*.py']
    else:
        raise NotImplementedError('Unsupported language %s' % language)


    for start_folder in folders:
        for root, subdirs, files in os.walk(os.path.join(base_folder, start_folder)):
            files = []
            for extension in extensions:
                files += glob(os.path.join(root, extension))
            
            if len(files) == 0:
                continue

            for file in files:
                file = os.path.relpath(file, base_folder)

                excluded = False
                for regex in exclude_patterns:
                    if re.search(regex, file):
                        excluded = True
                        break

                if excluded:
                    continue

                yield file

def write_docstring(file, docstring, language=None, add_shebang=False):
    global base_folder

    # TODO : Would be better to use """ in Python and /**/ in cpp.
    # But I don't want to spend time on file aprsing. There must be a tool that does that.
    if language == 'cpp':
        skip_patterns = []
        comment_pattern = [r'^\s*//(.*)', r'^\s+$']
        shebang = ''
    elif language == 'python':
        skip_patterns = []
        comment_pattern = [r'^\s*#(.*)', r'^\s+$']
        shebang = '#!/usr/bin/env python3\n\n' if add_shebang else ''
    else:
        raise NotImplementedError('Unsupported language %s' % language)
    file = os.path.join(base_folder, file)
    with open(file, 'r') as f:
        start_line = 0
        comment_lines = 0
        skip_done = False
        line_no = -1
        all_lines = []
        header_finished = False
        for line in f.readlines():
            line_no +=1
            all_lines.append(line)
            if header_finished:
                continue

            skipped = False
            if not skip_done:
                for pattern in skip_patterns:
                    if re.match(pattern, line):
                        start_line += 1
                        skipped = True
                        break
            
            if skipped:
                continue

            for pattern in comment_pattern:
                is_comment = False
                if re.match(pattern, line):
                    is_comment = True
                    break
            if is_comment:
                if skip_done == False:
                    start_line = line_no
                skip_done = True
                comment_lines += 1
            else:
                header_finished = True

    for i in range(comment_lines):
        all_lines.pop(start_line)
    docstring = format_docstring(docstring, language)
    
    if language == 'cpp':
        filename = '//    '+os.path.basename(file)
        new_header = """%s%s%s
//
//   - License : MIT - See LICENSE file.
//   - Project : Scrutiny Debugger (github.com/scrutinydebugger)
//
//   Copyright (c) 2021-%s Scrutiny Debugger
""" % (shebang, filename, docstring, datetime.now().strftime('%Y'))

    elif language == 'python':
        filename = '#    '+os.path.basename(file)
        new_header = """%s%s%s
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger)
#
#   Copyright (c) 2021-%s Scrutiny Debugger
""" % (shebang, filename, docstring, datetime.now().strftime('%Y'))
    
    header_lines = new_header.split('\n')
    header_lines.reverse()

    for line_to_insert in header_lines:
        all_lines.insert(start_line, line_to_insert+'\n')

    with open(file, 'w') as f:
        f.writelines(all_lines)

def format_docstring(docstring, language):
    chunk_size = 80
    space = 8
    lines = []
    done = False
    while not done:
        next_line_break = docstring.find('\n')
        if len(docstring) <= chunk_size:
            done =True
            lines.append(docstring[0:].strip())
        elif next_line_break >= 0 and next_line_break <= chunk_size:
            lines.append(docstring[0:next_line_break+1].strip())
            docstring=docstring[next_line_break+1:]
        else:
            i=0
            while True:
                if len(docstring) <= chunk_size+i:
                    lines.append(docstring[0:])
                    done = True
                    break
                elif docstring[chunk_size+i] in [' ', '\n']: 
                    lines.append(docstring[0:chunk_size+i].strip())
                    docstring=docstring[chunk_size+i:]
                    break
                else:
                    i += 1
    docstring = '\n'.join(lines)
    if docstring:
        docstring = '\n' + docstring

    if language == 'cpp':
        docstring = docstring.replace('\n', '\n//'+' '*space)
    elif language == 'python':
        docstring = docstring.replace('\n', '\n#'+' '*space)
    else:
        raise NotImplementedError('Unsupported language %s' % language)
    return docstring


def main():
    parser = argparse.ArgumentParser(prog = __file__)
    parser.add_argument('action',  help='Action to execute', choices=['make', 'write'])
    parser.add_argument('def_file',  help='Definition file to read or make')
    parser.add_argument('language',  help='Language file to read', choices=['cpp', 'python'])
    
    args = parser.parse_args()

    if os.path.isfile(args.def_file):
        with open(args.def_file, 'r') as f:
            filemap = json.load(f)
    else:
        filemap = {}
    
    if args.language == 'python':
        files = get_files(['python', 'lib'], args.language)
    elif args.language == 'cpp':
        files = get_files(['lib'], args.language)
    else:
        raise NotImplementedError('Unsupported language %s' % args.language)

    if args.action == 'make':
        for file in files:
            if file not in filemap:
                filemap[file] = {}

            if 'docstring' not in filemap[file]:
                filemap[file]['docstring'] = ''

        with open(args.def_file, 'w') as f:
            json.dump(filemap, f, indent=4)
    
    elif args.action == 'write':
        for file in files:
            entry = filemap[file] if file in filemap else {}

            docstring = entry['docstring'] if 'docstring' in entry else ''
            add_shebang = entry['add_shebang'] if 'add_shebang' in entry else False
            write_docstring(file, docstring, args.language, add_shebang)
    else:
        raise Exception('Unknown action %s' % args.action)


if __name__ == '__main__':
    main()