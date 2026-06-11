import zarr
from zarr.storage import ZipStore

file_path = r"D:\Docs\Tuchin\Test\project_newest\Default_project.bmip"

print("Открываем Zarr архив...")
store = ZipStore(file_path, mode='r')
root = zarr.open_group(store=store, mode='r')

# Эта команда распечатает всё дерево датаблоков и массивов!
print(f'project path: {file_path}')
print(root.tree())

store.close()