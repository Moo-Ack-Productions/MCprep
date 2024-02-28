import ast
from pathlib import Path
import polib

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

def main():
    path = Path(".")
    extracted_strings = {}
    for p in path.rglob("*.py"):
        with open(p, 'r') as f:
            root = ast.parse(f.read())
            visitor = TranslateCallVisitor()
            visitor.visit(root)
            if len(visitor.keys):
                extracted_strings[str(p)] = visitor.keys
    
    po = polib.POFile()
    po.metadata = {
        'Project-Id-Version': '1.0',
        'Report-Msgid-Bugs-To': 'you@example.com',
        'POT-Creation-Date': '2007-10-18 14:00+0100',
        'PO-Revision-Date': '2007-10-18 14:00+0100',
        'Last-Translator': 'you <you@example.com>',
        'Language-Team': 'English <yourteam@example.com>',
        'MIME-Version': '1.0',
        'Content-Type': 'text/plain; charset=utf-8',
        'Content-Transfer-Encoding': '8bit',
    }
    for file, keys in extracted_strings.items():
        for msgid, lineno in keys.items():
            entry = polib.POEntry(
                msgid=msgid,
                msgstr=u'',
                occurrences=[(file, n) for n in lineno]
            )
            po.append(entry)
            po.save("mcprep.pot")
