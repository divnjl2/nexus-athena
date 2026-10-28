"""Structural protection of existing named tests, not semantic equivalence."""
import ast


def _definitions(text):
    found, scope = {}, []
    class Visitor(ast.NodeVisitor):
        def visit_ClassDef(self, node):
            scope.append(node.name)
            self.generic_visit(node)
            scope.pop()

        def visit_FunctionDef(self, node):
            scope.append(node.name)
            if node.name.startswith('test'):
                found.setdefault(tuple(scope), []).append(ast.dump(node, include_attributes=False))
            self.generic_visit(node)
            scope.pop()

        visit_AsyncFunctionDef = visit_FunctionDef
    Visitor().visit(ast.parse(text))
    return found


def preserve_named_tests(old: str, new: str, name: str) -> None:
    if not old or old == new:
        return
    try:
        before, after = _definitions(old), _definitions(new)
    except (SyntaxError, ValueError, RecursionError) as error:
        raise ValueError('cannot establish named-test preservation for ' + name) from error
    for key, definitions in before.items():
        if after.get(key) != definitions:
            raise ValueError('existing named test changed, removed or redefined: ' + name + '::' + '::'.join(key))
