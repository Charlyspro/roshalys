import os

from django.core.files.move import file_move_safe
from django.core.files.storage import FileSystemStorage
from django.utils._os import safe_makedirs


class NoLockFileSystemStorage(FileSystemStorage):
    """
    FileSystemStorage que no usa fcntl.flock (incompatible con Wasmer Edge).

    Replica el _save() de Django 5.2 sin llamar a locks.lock()/locks.unlock().
    """

    def _save(self, name, content):
        full_path = self.path(name)

        directory = os.path.dirname(full_path)
        try:
            if self.directory_permissions_mode is not None:
                safe_makedirs(directory, self.directory_permissions_mode, exist_ok=True)
            else:
                os.makedirs(directory, exist_ok=True)
        except FileExistsError:
            raise FileExistsError("%s exists and is not a directory." % directory)

        while True:
            try:
                if hasattr(content, "temporary_file_path"):
                    file_move_safe(
                        content.temporary_file_path(),
                        full_path,
                        allow_overwrite=self._allow_overwrite,
                    )
                else:
                    open_flags = (
                        os.O_WRONLY
                        | os.O_CREAT
                        | os.O_EXCL
                        | getattr(os, "O_BINARY", 0)
                    )
                    if self._allow_overwrite:
                        open_flags = open_flags & ~os.O_EXCL | os.O_TRUNC
                    fd = os.open(full_path, open_flags, 0o666)
                    _file = None
                    try:
                        for chunk in content.chunks():
                            if _file is None:
                                mode = "wb" if isinstance(chunk, bytes) else "wt"
                                _file = os.fdopen(fd, mode)
                            _file.write(chunk)
                    finally:
                        if _file is not None:
                            _file.close()
                        else:
                            os.close(fd)
            except FileExistsError:
                name = self.get_available_name(name)
                full_path = self.path(name)
            else:
                break

        if self.file_permissions_mode is not None:
            os.chmod(full_path, self.file_permissions_mode)

        name = os.path.relpath(full_path, self.location)
        self._ensure_location_group_id(full_path)
        return str(name).replace("\\", "/")