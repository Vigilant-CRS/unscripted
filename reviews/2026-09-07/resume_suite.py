import ast
from pathlib import Path
import runpy

path = Path(__file__).resolve().parents[2] / 'tests/test_scenarios.py'
tree = ast.parse(path.read_text())
assignment = next(node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'suite' for t in node.targets))
names = [node.id for node in assignment.value.elts]
start = names.index('test_packaging_manifest_covers_every_data_file')
namespace = runpy.run_path(str(path), run_name='review_resume')
print(f'Resuming at {start + 1}/{len(names)} after moving review artifacts out of packaged docs.')
for index, name in enumerate(names[start:], start=start + 1):
    print(f'RUN {index}/{len(names)} {name}', flush=True)
    namespace[name]()
print(f'All remaining {len(names)-start} tests passed; earlier {start} passed in the original run.')
