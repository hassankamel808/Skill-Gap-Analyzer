import pathlib
p = pathlib.Path('dashboard/streamlit_app.py')
t = p.read_text(encoding='utf-8')
t = t.replace('use_container_width=True', 'width="stretch"')
t = t.replace('use_container_width=False', 'width="content"')
p.write_text(t, encoding='utf-8')
print('Done. Replacements in file:', t.count('width='))
