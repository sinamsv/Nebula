import os
import re
import json
import uuid
import shutil
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

class ProjectError(Exception):
    """Base exception for all project-related errors."""
    pass

class ProjectNotFoundError(ProjectError):
    """Raised when a project, chat, or file is not found."""
    pass

class ProjectPermissionError(ProjectError):
    """Raised when access is denied (not the owner)."""
    pass

class ProjectValidationError(ProjectError):
    """Raised when validation of input parameters fails."""
    pass

class ProjectStorageError(ProjectError):
    """Raised on any I/O, OS, or formatting filesystem error."""
    pass


def sanitize_username(username: str) -> str:
    """Sanitizes username to be filesystem-safe, matching core pattern."""
    if not username:
        raise ProjectValidationError("Username cannot be empty.")
    # core/auth.py checks USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{3,32}$')
    # We replace any non-alphanumeric, non-underscore with underscore.
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', username)
    if not sanitized:
        sanitized = "user"
    return sanitized


def get_projects_root() -> str:
    """Gets the configured projects data root path from env, defaulting to 'projects'."""
    return os.getenv("PROJECTS_DIR", "projects")


class ProjectStore:
    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = root_dir or get_projects_root()

    def _get_user_dir(self, username: str) -> str:
        sanitized = sanitize_username(username)
        return os.path.join(self.root_dir, sanitized)

    def _get_project_dir(self, username: str, project_id: str) -> str:
        # Validate project_id is a valid UUID string
        try:
            uuid.UUID(project_id)
        except ValueError:
            raise ProjectValidationError(f"Invalid project_id format. Expected UUID, got '{project_id}'")

        user_dir = os.path.abspath(self._get_user_dir(username))
        project_dir = os.path.abspath(os.path.join(user_dir, project_id))

        # Direct path traversal prevention check
        if not project_dir.startswith(user_dir + os.sep) and project_dir != user_dir:
            raise ProjectValidationError("Security validation failed: Invalid path traversal detected.")

        return project_dir

    def create_project(self, name: str, description: str, owner: str) -> Dict[str, Any]:
        """Creates a new project on disk and returns its metadata."""
        if not name.strip():
            raise ProjectValidationError("Project name cannot be empty.")

        project_uuid = str(uuid.uuid4())
        project_dir = self._get_project_dir(owner, project_uuid)

        try:
            os.makedirs(project_dir, exist_ok=True)
            os.makedirs(os.path.join(project_dir, "knowledge"), exist_ok=True)
            os.makedirs(os.path.join(project_dir, "chats"), exist_ok=True)
        except OSError as e:
            raise ProjectStorageError(f"Failed to create project directories: {e}")

        now = datetime.now(timezone.utc).isoformat()
        metadata = {
            "id": project_uuid,
            "name": name,
            "description": description,
            "owner": owner,
            "created_at": now,
            "updated_at": now
        }

        # Save metadata.json
        metadata_path = os.path.join(project_dir, "metadata.json")
        try:
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        except OSError as e:
            raise ProjectStorageError(f"Failed to write metadata.json: {e}")

        # Create empty instruction.md
        instruction_path = os.path.join(project_dir, "instruction.md")
        try:
            with open(instruction_path, "w", encoding="utf-8") as f:
                f.write("")
        except OSError as e:
            raise ProjectStorageError(f"Failed to create instruction.md: {e}")

        return metadata

    def get_project_metadata(self, username: str, project_id: str) -> Dict[str, Any]:
        """Reads project metadata and verifies ownership."""
        project_dir = self._get_project_dir(username, project_id)
        metadata_path = os.path.join(project_dir, "metadata.json")

        if not os.path.isdir(project_dir) or not os.path.exists(metadata_path):
            raise ProjectNotFoundError(f"Project '{project_id}' not found.")

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise ProjectStorageError(f"Failed to read metadata.json: {e}")

        # Enforce owner-only access control
        if metadata.get("owner") != username:
            raise ProjectPermissionError("Access denied. You do not own this project.")

        return metadata

    def list_projects(self, username: str) -> List[Dict[str, Any]]:
        """Lists metadata of all projects owned by the user."""
        user_dir = self._get_user_dir(username)
        if not os.path.exists(user_dir):
            return []

        projects = []
        try:
            entries = os.listdir(user_dir)
        except OSError as e:
            raise ProjectStorageError(f"Failed to list user directory: {e}")

        for entry in entries:
            # Check if directory name is a valid UUID
            try:
                uuid.UUID(entry)
            except ValueError:
                continue  # skip non-project directories or files

            try:
                metadata = self.get_project_metadata(username, entry)
                projects.append(metadata)
            except (ProjectNotFoundError, ProjectPermissionError):
                continue  # skip corrupted or unowned directories

        # Sort projects by updated_at descending
        projects.sort(key=lambda p: p.get("updated_at", ""), reverse=True)
        return projects

    def delete_project(self, username: str, project_id: str) -> None:
        """Deletes project folder and all contents for the authenticated owner."""
        # This call verifies existence and ownership
        self.get_project_metadata(username, project_id)

        project_dir = self._get_project_dir(username, project_id)
        try:
            shutil.rmtree(project_dir)
        except OSError as e:
            raise ProjectStorageError(f"Failed to delete project directory: {e}")

    def update_instruction(self, username: str, project_id: str, instruction: str) -> None:
        """Updates instruction.md and updates the project's updated_at timestamp."""
        self.get_project_metadata(username, project_id)  # verify existence & owner

        project_dir = self._get_project_dir(username, project_id)
        instruction_path = os.path.join(project_dir, "instruction.md")

        try:
            with open(instruction_path, "w", encoding="utf-8") as f:
                f.write(instruction)
        except OSError as e:
            raise ProjectStorageError(f"Failed to update instruction.md: {e}")

        self._touch_project(username, project_id)

    def read_instruction(self, username: str, project_id: str) -> str:
        """Reads the project instruction.md."""
        self.get_project_metadata(username, project_id)  # verify existence & owner

        project_dir = self._get_project_dir(username, project_id)
        instruction_path = os.path.join(project_dir, "instruction.md")

        if not os.path.exists(instruction_path):
            return ""

        try:
            with open(instruction_path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError as e:
            raise ProjectStorageError(f"Failed to read instruction.md: {e}")

    def save_knowledge_file(self, username: str, project_id: str, filename: str, content_bytes: bytes) -> None:
        """Saves or overwrites a knowledge file inside project knowledge/."""
        self.get_project_metadata(username, project_id)  # verify existence & owner

        # Strict filename sanitization to prevent directory traversal within the project directory
        clean_filename = os.path.basename(filename)
        if not clean_filename or clean_filename in (".", ".."):
            raise ProjectValidationError(f"Invalid knowledge filename '{filename}'")

        project_dir = self._get_project_dir(username, project_id)
        file_path = os.path.join(project_dir, "knowledge", clean_filename)

        try:
            with open(file_path, "wb") as f:
                f.write(content_bytes)
        except OSError as e:
            raise ProjectStorageError(f"Failed to save knowledge file: {e}")

        self._touch_project(username, project_id)

    def list_knowledge_files(self, username: str, project_id: str) -> List[str]:
        """Lists filenames under knowledge/."""
        self.get_project_metadata(username, project_id)  # verify existence & owner

        project_dir = self._get_project_dir(username, project_id)
        knowledge_dir = os.path.join(project_dir, "knowledge")

        if not os.path.isdir(knowledge_dir):
            return []

        try:
            return os.listdir(knowledge_dir)
        except OSError as e:
            raise ProjectStorageError(f"Failed to list knowledge files: {e}")

    def read_knowledge_files_contents(self, username: str, project_id: str) -> Dict[str, str]:
        """Reads and decodes all knowledge files under knowledge/ as text."""
        self.get_project_metadata(username, project_id)

        project_dir = self._get_project_dir(username, project_id)
        knowledge_dir = os.path.join(project_dir, "knowledge")

        if not os.path.isdir(knowledge_dir):
            return {}

        try:
            filenames = os.listdir(knowledge_dir)
        except OSError as e:
            raise ProjectStorageError(f"Failed to list knowledge files: {e}")

        contents = {}
        for filename in filenames:
            file_path = os.path.join(knowledge_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    contents[filename] = f.read()
            except OSError as e:
                raise ProjectStorageError(f"Failed to read knowledge file '{filename}': {e}")

        return contents

    def create_chat(self, username: str, project_id: str, title: Optional[str] = None) -> Dict[str, Any]:
        """Creates a project-scoped chat file."""
        self.get_project_metadata(username, project_id)

        chat_uuid = str(uuid.uuid4())
        project_dir = self._get_project_dir(username, project_id)
        chats_dir = os.path.join(project_dir, "chats")
        chat_path = os.path.join(chats_dir, f"{chat_uuid}.json")

        now = datetime.now(timezone.utc).isoformat()
        chat_data = {
            "chat_id": chat_uuid,
            "title": title or "New Chat",
            "created_at": now,
            "last_message_at": now,
            "messages": []
        }

        try:
            with open(chat_path, "w", encoding="utf-8") as f:
                json.dump(chat_data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            raise ProjectStorageError(f"Failed to create chat file: {e}")

        self._touch_project(username, project_id)
        return chat_data

    def get_chat(self, username: str, project_id: str, chat_id: str) -> Dict[str, Any]:
        """Gets chat detail from JSON file."""
        self.get_project_metadata(username, project_id)

        # Validate chat_id is UUID to prevent traversal
        try:
            uuid.UUID(chat_id)
        except ValueError:
            raise ProjectValidationError(f"Invalid chat_id format. Expected UUID, got '{chat_id}'")

        project_dir = self._get_project_dir(username, project_id)
        chat_path = os.path.join(project_dir, "chats", f"{chat_id}.json")

        if not os.path.exists(chat_path):
            raise ProjectNotFoundError(f"Chat '{chat_id}' not found.")

        try:
            with open(chat_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise ProjectStorageError(f"Failed to read chat file: {e}")

    def list_chats(self, username: str, project_id: str) -> List[Dict[str, Any]]:
        """Lists summaries of chats in the project sorted by last_message_at descending."""
        self.get_project_metadata(username, project_id)

        project_dir = self._get_project_dir(username, project_id)
        chats_dir = os.path.join(project_dir, "chats")

        if not os.path.exists(chats_dir):
            return []

        try:
            filenames = os.listdir(chats_dir)
        except OSError as e:
            raise ProjectStorageError(f"Failed to list chats directory: {e}")

        chats = []
        for filename in filenames:
            if not filename.endswith(".json"):
                continue
            chat_id = filename[:-5]
            try:
                chat_data = self.get_chat(username, project_id, chat_id)
                chats.append({
                    "chat_id": chat_data["chat_id"],
                    "title": chat_data["title"],
                    "created_at": chat_data["created_at"],
                    "last_message_at": chat_data["last_message_at"]
                })
            except (ProjectValidationError, ProjectNotFoundError, ProjectStorageError):
                continue

        chats.sort(key=lambda c: c.get("last_message_at", ""), reverse=True)
        return chats

    def append_chat_message(self, username: str, project_id: str, chat_id: str, role: str, content: str, token_count: int = 0) -> Dict[str, Any]:
        """Appends a message to the project chat's JSON file and updates timestamps."""
        chat_data = self.get_chat(username, project_id, chat_id)

        now = datetime.now(timezone.utc).isoformat()
        message_obj = {
            "role": role,
            "content": content,
            "timestamp": now,
            "token_count": token_count
        }
        chat_data["messages"].append(message_obj)
        chat_data["last_message_at"] = now

        project_dir = self._get_project_dir(username, project_id)
        chat_path = os.path.join(project_dir, "chats", f"{chat_id}.json")

        try:
            with open(chat_path, "w", encoding="utf-8") as f:
                json.dump(chat_data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            raise ProjectStorageError(f"Failed to write chat file: {e}")

        self._touch_project(username, project_id)
        return chat_data

    def _touch_project(self, username: str, project_id: str) -> None:
        """Touches the project, updating its updated_at timestamp in metadata.json."""
        project_dir = self._get_project_dir(username, project_id)
        metadata_path = os.path.join(project_dir, "metadata.json")

        if not os.path.exists(metadata_path):
            return

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)

            metadata["updated_at"] = datetime.now(timezone.utc).isoformat()

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        except Exception:
            # Squelch internally, but on core I/O operations we always raise explicitly
            pass
