import ast
from datetime import datetime, tzinfo, timedelta
import time
from pathlib import Path
import polib

from bpy_addon_build.api import BabContext

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

MCPREP_VERSION = "3.6"
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

def pre_build(ctx: BabContext):
    print("Building POT...")
    path = Path(ctx.current_path)
    extracted_strings = {}
    for p in path.rglob("*.py"):
        with open(p, 'r') as f:
            root = ast.parse(f.read())
            visitor = TranslateCallVisitor()
            visitor.visit(root)
            if len(visitor.keys):
                extracted_strings[f"{str(p)}"] = visitor.keys
    
    po = polib.POFile()
    po.metadata = {
        "Project-Id-Version": MCPREP_VERSION,
        "Report-Msgid-Bugs-To": MCPREP_ISSUE_TRACKER,
        "POT-Creation-Date": datetime.fromtimestamp(timestamp, ltz).strftime('%Y-%m-%d %H:%M%z'),
        "PO-Revision-Date": "YEAR-MO-DA HO:MI+ZONE",
        "Last-Translator": "FULL NAME <EMAIL@ADDRESS>",
        "Language-Team": "LANGUAGE <LL@li.org>",
        "Language": "",
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=CHARSET",
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

if __name__ == "__main__":
    main()
