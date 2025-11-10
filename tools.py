def get_extension(url: str) -> str :
    extension = url.split(".")[-1]
    return extension[:-1] if extension.endswith("/") else extension
