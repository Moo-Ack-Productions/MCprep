import ast
import re
from datetime import datetime, tzinfo, timedelta
import time
from pathlib import Path
from typing import Optional
import polib

from bpy_addon_build.api import BabContext, BpyError

class TranslateCallVisitor(ast.NodeVisitor):
    def __init__(self):
        self.keys = {}

    def visit_Call(self, node: ast.Call):
        attr = node.func
        if not isinstance(attr, ast.Attribute):
            self.generic_visit(node)
            return
        
        # Check if the function we're calling 
        # is an attribute of env
        attr_value = attr.value
        if not isinstance(attr_value, ast.Name):
            self.generic_visit(node)
            return
        if attr_value.id != 'env':
            self.generic_visit(node)
            return
        del attr_value # delete as no longer needed
        
        # Check if we're calling env._
        attr_name = attr.attr
        if attr_name != '_':
            self.generic_visit(node)
            return
        del attr_name # delete as no longer needed

        if len(node.args):
            # env._ only accepts one argument
            msgid = node.args[0]
            if not isinstance(msgid, ast.Constant):
                self.generic_visit(node)
                return
            if msgid.value not in self.keys:
                self.keys[msgid.value] = [msgid.lineno]
            else:
                self.keys[msgid.value].append(msgid.lineno)
        self.generic_visit(node)

VERSION_REGEX = r'"version"\s*:\s*(\(.*?\))'
MCPREP_ISSUE_TRACKER = "https://github.com/Moo-Ack-Productions/MCprep/issues"

# Copied from here:
# https://github.com/shibukawa/sphinx/blob/master/sphinx/builders/gettext.py
timestamp = time.time()
tzdelta = datetime.fromtimestamp(timestamp) - datetime.utcfromtimestamp(timestamp)
class LocalTimeZone(tzinfo):

    def __init__(self, *args, **kw):
        super(LocalTimeZone, self).__init__(*args, **kw)
        self.tzdelta = tzdelta

    def utcoffset(self, dt):
        return self.tzdelta

    def dst(self, dt):
        return timedelta(0)

ltz = LocalTimeZone()

def pre_build(ctx: BabContext) -> Optional[BpyError]:
    print("Building POT...")
    path = Path(ctx.current_path)
    extracted_strings = {}

    version_str: Optional[str] = None
    with open(Path(ctx.current_path, "__init__.py"), 'r') as f:
        for line in f:
            if re.search(VERSION_REGEX, line):
                version_str = line
                break

    if not version_str:
        return BpyError("Can't extract version from __init__.py!")
    
    try:
        # Step by step breakdown:
        # 1. Split the string '"version": (...)' to 
        #    "version" and (...)
        # 2. Take the second element, remove extra whitespace,
        #    and remove the first character and last 2 characters
        #    (parenthesis and trailing comma)
        # 3. Split that final string by the comma
        # 4. Do a small generator that strips each element
        #    of extra whitespace
        # 5. Join them up with a '.' in between
        processed_version_string = '.'.join(tuple(
            v.strip() for v in version_str.strip()
                                .split(':')[1]
                                .strip()[1:][:-2]
                                .split(',')))
    except Exception:
        return BpyError(f"Couldn't convert {version_str}!")

    for p in path.rglob("*.py"):
        with open(p, 'r') as f:
            root = ast.parse(f.read())
            visitor = TranslateCallVisitor()
            visitor.visit(root)
            if len(visitor.keys):
                extracted_strings[f"{str(p)}"] = visitor.keys
    
    po = polib.POFile()
    po.metadata = {
        "Project-Id-Version": processed_version_string,
        "Report-Msgid-Bugs-To": MCPREP_ISSUE_TRACKER,
        "POT-Creation-Date": datetime.fromtimestamp(timestamp, ltz).strftime('%Y-%m-%d %H:%M%z'),
        "PO-Revision-Date": "YEAR-MO-DA HO:MI+ZONE",
        "Last-Translator": "FULL NAME <EMAIL@ADDRESS>",
        "Language-Team": "LANGUAGE <LL@li.org>",
        "Language": "",
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=UTF-8",
        "Content-Transfer-Encoding": "8bit",
    }
    for file, keys in extracted_strings.items():
        for msgid, lineno in keys.items():
            entry = polib.POEntry(
                msgid=msgid,
                msgstr=u'',
                occurrences=[(file, n) for n in lineno]
            )
            po.append(entry)
            po.save(str(ctx.current_path) + "/MCprep_resources/Languages/mcprep.pot")
    return None
