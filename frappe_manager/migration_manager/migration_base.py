from typing import Protocol, runtime_checkable

from frappe_manager.migration_manager.backup_manager import BackupManager
from frappe_manager.migration_manager.version import Version
from frappe_manager import CLI_DIR
from frappe_manager.logger import log

@runtime_checkable
class MigrationBase(Protocol):

    version: Version = Version("0.0.0")
    skip: bool = False
    migration_executor = None
    backup_manager: BackupManager  # Declare the backup_manager variable
    logger = log.get_logger()

    def __init__(self):
        self.backup_manager = BackupManager(str(self.version))  # Assign the value to backup_manager

    def up(self):
        pass

    def down(self):
        pass
