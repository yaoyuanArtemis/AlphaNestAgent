from pathlib import Path
import os


basePath = Path("")


def read_file(name:str) -> str:

    print(f"read_file{name}")
    try:
        with open(basePath / name,"r") as f:
            content = f.read()
        return content
    except Exception as e:
        return f"An error occured:{e}"


def list_files() -> list[str]:
    print("(list_file)")
    file_list = []
    for item in basePath.rglob("*"):
        if item.is_file():
            file_list.append(str(item.relative_to(basePath)))

    return file_list


def rename_name(name:str,new_name:str) -> str:
    print(f"rename_file{name} -> {new_name}")
    try:
        new_path = basePath / new_name
        if not str(new_path).startswith(str(basePath)):
            return "Error: new_name is outside basePath."

        os.makedirs(new_path.parent, exist_ok=True)
        os.rename(basePath / name, new_path)
        return f"File '{name}' successfully renamed to '{new_name}'."
    except Exception as e:
        return f"An error occurred: {e}"